"""
Image extractor pipeline handler.

Migrated from ``extract_images_from_pdf`` in ``pdf_parser.py``.

Runs when ``profile.has_images`` is ``True``.  Populates ``ctx.image_map`` with
a ``{(year, question_number): "/images/<filename>"}`` mapping for each question
that has a diagram.

Supports two diagram formats:
* **Raster images** (block type=1 in PyMuPDF rawdict) — extracted directly.
* **Vector drawings** (PDF path/drawing primitives) — rendered to PNG via
  ``page.get_pixmap(clip=…)`` when no raster images are present.

Year detection supports banner formats from
``answers_block.normalise_year_banners``:
* ``UTME 2010 ECONOMICS QUESTIONS`` / ``2010 JAMB BIOLOGY QUESTIONS``
* Alternate: ``Mathematics 1983``, ``Biology 1990`` etc.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from app.extraction.core.profile import CapabilityProfile
from app.extraction.core.stages import ImageExtractionOutput
from app.extraction.resolvers.answers.answers_block import _YR_BANNER_ALT_RE, _YR_BANNER_RE

_INSTR_RE = re.compile(
    r"[Uu]se\s+the\s+diagram\b[^.]*?"
    r"(?:question[s]?\s+(\d+)(?:\s*(?:and|to)\s*(\d+))?"
    r"|the\s+question\s+that\s+follow)",
    re.IGNORECASE | re.DOTALL,
)
# Minimum diagram size (pixels) to avoid saving decorative lines/dividers.
_MIN_DIAG_HEIGHT = 25
_MIN_DIAG_WIDTH = 25


def _build_page_years(doc) -> Dict[int, Optional[str]]:
    """Return a ``{page_num: year_str}`` map using both banner formats."""
    page_year: Dict[int, Optional[str]] = {}
    last_year: Optional[str] = None
    for page_num in range(len(doc)):
        text = doc[page_num].get_text()
        yr_m = _YR_BANNER_RE.search(text)
        if yr_m:
            last_year = yr_m.group(1) or yr_m.group(2)
        else:
            yr_m_alt = _YR_BANNER_ALT_RE.search(text)
            if yr_m_alt:
                last_year = yr_m_alt.group(1)
        page_year[page_num] = last_year
    return page_year


def _cluster_rects(rects: list, gap: float = 15.0) -> List[List[float]]:
    """
    Merge a list of ``fitz.Rect`` objects that are within *gap* pixels of each
    other vertically.  Returns ``[[y0, y1, x0, x1], …]`` clusters.
    """
    if not rects:
        return []
    sorted_r = sorted(rects, key=lambda r: r.y0)
    clusters: List[List[float]] = []
    for r in sorted_r:
        if clusters and r.y0 <= clusters[-1][1] + gap:
            c = clusters[-1]
            c[0] = min(c[0], r.y0)
            c[1] = max(c[1], r.y1)
            c[2] = min(c[2], r.x0)
            c[3] = max(c[3], r.x1)
        else:
            clusters.append([r.y0, r.y1, r.x0, r.x1])
    return clusters


def _extract_vector_images(
    doc,
    stem: str,
    images_dir: Path,
    page_year: Dict[int, Optional[str]],
) -> Dict[Tuple[Optional[str], int], str]:
    """
    Render vector-drawing diagram regions as PNG files and map them to questions.

    Used as a fallback when the PDF contains no raster image blocks (all diagrams
    are drawn as PDF path/drawing primitives).

    Strategy
    --------
    For each page:
    1. Split drawing paths into left- and right-column groups (by centre-x).
    2. Cluster paths within each column by vertical proximity.
    3. Filter out headers, footers, and thin decorative lines.
    4. For each cluster, render the page clip region to a PNG via
       ``page.get_pixmap()``.
    5. Associate the image with the question whose number appears at the largest
       y0 that is still ≤ the cluster's y1 (i.e. the last question that started
       at or within the diagram region).
    """
    import fitz as _fitz

    q_to_image: Dict[Tuple[Optional[str], int], str] = {}

    for page_num in range(len(doc)):
        page = doc[page_num]
        drawings = page.get_drawings()
        if not drawings:
            continue

        page_w = page.rect.width
        page_h = page.rect.height
        col_split = page_w / 2
        year = page_year[page_num]

        # Collect question-number positions: (y0, x0, qnum)
        q_positions: List[Tuple[float, float, int]] = []
        for b in page.get_text("blocks"):
            if b[6] != 0:
                continue
            m = re.match(r"^\s*(\d{1,3})\.\s", b[4])
            if m:
                q_positions.append((b[1], b[0], int(m.group(1))))

        if not q_positions:
            continue

        # Split drawing rects into columns; skip degenerate paths
        left_rects, right_rects = [], []
        for d in drawings:
            r = d.get("rect")
            if r is None or r.height < 3 or r.width < 3:
                continue
            center_x = (r.x0 + r.x1) / 2
            if center_x < col_split:
                left_rects.append(r)
            else:
                right_rects.append(r)

        for col_rects, col_side in [(left_rects, "L"), (right_rects, "R")]:
            clusters = _cluster_rects(col_rects, gap=15.0)
            for cy0, cy1, cx0, cx1 in clusters:
                height = cy1 - cy0
                width = cx1 - cx0
                # Skip thin decorative dividers and header/footer rules
                if height < _MIN_DIAG_HEIGHT or width < _MIN_DIAG_WIDTH:
                    continue
                # Skip full-page-width horizontal bands (likely page borders)
                if width > page_w * 0.8 and height < 30:
                    continue

                # Find the associated question: latest q_num whose y0 <= cluster.y1
                col_qs = [
                    (qy, qnum)
                    for qy, qx, qnum in q_positions
                    if (col_side == "L" and qx < col_split)
                    or (col_side == "R" and qx >= col_split)
                ]
                candidates = [(qy, qnum) for qy, qnum in col_qs if qy <= cy1 + 10]
                if not candidates:
                    continue
                _, qnum = max(candidates, key=lambda t: t[0])

                key: Tuple[Optional[str], int] = (year, qnum)
                if key in q_to_image:
                    continue  # already have an image for this question

                # Render the clipped region to PNG (2× zoom for quality)
                pad = 5
                clip = _fitz.Rect(
                    max(0.0, cx0 - pad),
                    max(0.0, cy0 - pad),
                    min(page_w, cx1 + pad),
                    min(page_h, cy1 + pad),
                )
                mat = _fitz.Matrix(2, 2)
                pix = page.get_pixmap(matrix=mat, clip=clip)
                fname = f"{stem}_p{page_num + 1}_vec_{col_side}_{qnum}.png"
                (images_dir / fname).write_bytes(pix.tobytes("png"))
                q_to_image[key] = f"/images/{fname}"

    return q_to_image


def _extract_images(
    doc,  # fitz.Document
    stem: str,
    images_dir: Path,
) -> Dict[Tuple[Optional[str], int], str]:
    """
    Core image-extraction logic operating on an already-open ``fitz.Document``.

    Strategy
    --------
    Pass 1 — determine the year label per page from year-section banners
             (both ``YYYY JAMB SUBJECT QUESTIONS`` and ``Subject YYYY`` formats).
    Pass 2 — extract and save raw raster image bytes; build ``page_images`` map.
    Pass 3 — parse "Use the diagram…" instructions and associate them with
              the nearest image at or below the instruction on the same page
              (or the first image on the following page).
    Pass 4 — if no raster images were found, fall back to vector-drawing
              extraction via ``_extract_vector_images()``.
    """
    images_dir.mkdir(parents=True, exist_ok=True)

    # Pass 1: year labels per page (supports both banner formats)
    page_year = _build_page_years(doc)

    # Pass 2: raw raster image bytes
    page_images: Dict[int, List[Tuple[float, str]]] = {}
    for page_num in range(len(doc)):
        page = doc[page_num]
        raw = page.get_text("rawdict")
        imgs: List[Tuple[float, str]] = []
        seq = 0
        for block in raw.get("blocks", []):
            if block.get("type") != 1:
                continue
            raw_bytes: bytes = block.get("image", b"")
            if not raw_bytes:
                continue
            y0: float = block["bbox"][1]
            ext = (block.get("ext") or "png").lower()
            if ext not in ("png", "jpeg", "jpg", "jpx", "jp2", "gif", "bmp", "tiff"):
                ext = "png"
            fname = f"{stem}_p{page_num + 1}_{seq}.{ext}"
            (images_dir / fname).write_bytes(raw_bytes)
            imgs.append((y0, f"/images/{fname}"))
            seq += 1
        page_images[page_num] = sorted(imgs, key=lambda t: t[0])

    # Pass 3: match "Use the diagram…" instructions to raster images
    q_to_image: Dict[Tuple[Optional[str], int], str] = {}
    for page_num in range(len(doc)):
        page = doc[page_num]
        full_text = page.get_text()
        year = page_year[page_num]

        text_blocks = sorted(page.get_text("blocks"), key=lambda b: b[1])
        anchor_ys = [
            b[1]
            for b in text_blocks
            if b[6] == 0 and re.search(r"use\s+the\s+diagram", b[4], re.IGNORECASE)
        ]

        instr_matches = list(_INSTR_RE.finditer(full_text))
        if not instr_matches:
            continue

        for idx, m in enumerate(instr_matches):
            q_start_str = m.group(1)
            q_end_str = m.group(2)
            instr_y0: float = anchor_ys[idx] if idx < len(anchor_ys) else 0.0

            if not q_start_str:
                rest = full_text[m.end():]
                nq = re.search(r"(\d{1,3})\.", rest)
                if nq:
                    q_start = q_end = int(nq.group(1))
                else:
                    continue
            else:
                q_start = int(q_start_str)
                q_end = int(q_end_str) if q_end_str else q_start

            candidates = [
                (iy, url)
                for iy, url in page_images.get(page_num, [])
                if iy >= instr_y0
            ]
            if not candidates:
                candidates = list(page_images.get(page_num + 1, []))
            if not candidates:
                continue

            _, img_url = candidates[0]
            for qnum in range(q_start, q_end + 1):
                key: Tuple[Optional[str], int] = (year, qnum)
                if key not in q_to_image:
                    q_to_image[key] = img_url

    # Pass 4: vector-drawing fallback when no raster images exist
    if not any(page_images.values()):
        vector_map = _extract_vector_images(doc, stem, images_dir, page_year)
        q_to_image.update(vector_map)

    return q_to_image


class ImageExtractorHandler:
    """
    Pipeline handler that extracts diagram images.

    Input:  ``doc`` (fitz.Document), ``pdf_path`` stem used for naming files.
    Output: ``ImageExtractionOutput`` with an ``image_map`` dict.

    Gated by ``profile.has_images``.
    """

    def can_handle(self, profile: CapabilityProfile) -> bool:
        return profile.has_images

    def process(self, doc: object, pdf_path: Path) -> ImageExtractionOutput:
        from app.core.config import settings

        images_dir = settings.IMAGES_DIR
        image_map = _extract_images(doc, pdf_path.stem, images_dir)
        return ImageExtractionOutput(image_map=image_map)
