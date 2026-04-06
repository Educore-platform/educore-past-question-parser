"""
Repair MCQ options whose numeric fractions are missing from the PDF text layer.

Some past papers (e.g. JAMB Biology dental-formula items) draw stacked fractions as
vector art while the text layer only contains tooth labels (I, C, pm, m) and commas.
PyMuPDF then returns strings like ``A. I , C , pm , m`` with no digits.

When Tesseract is installed on the system and ``pytesseract`` + ``Pillow`` are
installed in the venv, we render the option band at high resolution and OCR it,
then replace option text for matching questions.
"""

from __future__ import annotations

import io
import logging
import re
from typing import TYPE_CHECKING, Dict, List, Optional

if TYPE_CHECKING:
    import fitz

logger = logging.getLogger(__name__)

_OCR_ZOOM = 6.0

# Stem heuristics: dental-formula style questions
_DENTAL_STEM = re.compile(
    r"dental\s+formula",
    re.IGNORECASE,
)

# Options look like labels but contain no digit/fraction (vector fractions missing)
_OPTION_HAS_TOOTH_LABELS = re.compile(
    r"\bI\s*,\s*C\s*,\s*pm\s*,\s*m\b",
    re.IGNORECASE,
)
_HAS_NUMERIC_FRACTION = re.compile(r"\d\s*/\s*\d")
# Looser count for OCR strings (stacked fractions often glue digits)
_FRACTION_LIKE = re.compile(r"\d{1,2}\s*/\s*\d{1,2}")


def _try_imports():
    try:
        import pytesseract  # type: ignore[import-untyped]
        from PIL import Image  # type: ignore[import-untyped]
        return pytesseract, Image
    except ImportError:
        return None, None


def _question_needs_dental_ocr(q: dict) -> bool:
    stem = (q.get("question") or "").lower()
    if not _DENTAL_STEM.search(stem) or "carnivore" not in stem:
        return False
    opts: Dict[str, str] = q.get("options") or {}
    if not all(k in opts for k in ("A", "B", "C")):
        return False
    for letter in ("A", "B", "C"):
        t = opts[letter]
        if _HAS_NUMERIC_FRACTION.search(t):
            return False
        if not _OPTION_HAS_TOOTH_LABELS.search(t):
            return False
    return True


def _find_page_index(doc: "fitz.Document", question_number: int, stem_lower: str) -> Optional[int]:
    # Stem may join words; PDF often breaks "dental" / "formula" across lines.
    if "dental" not in stem_lower or "formula" not in stem_lower:
        return None
    qn_pat = re.compile(rf"(?:^|\s){question_number}\.")
    for i in range(len(doc)):
        text = doc[i].get_text()
        tl = text.lower()
        if "dental" not in tl or "formula" not in tl:
            continue
        if "carnivore" not in tl:
            continue
        if qn_pat.search(text):
            return i
    return None


def _option_row_rects(page: "fitz.Page") -> Optional[tuple[list["fitz.Rect"], float]]:
    """
    Return (list of row clips left-to-right for A/B/C, x1_max) or None.

    Rows are located via ``A.`` / ``B.`` / ``C.`` words in the same column as
    ``carnivores`` so each line can be OCR'd alone (clearer than one tall band).
    """
    import fitz

    words = page.get_text("words")
    carn_x0: Optional[float] = None
    carn_y1: Optional[float] = None
    for w in words:
        if "carnivore" in w[4].lower():
            carn_y1 = w[3]
            carn_x0 = w[0]
            break
    if carn_x0 is None or carn_y1 is None:
        return None

    col_left = 24.0 if carn_x0 < page.rect.width * 0.45 else 280.0
    col_right = page.rect.width * 0.52 if carn_x0 < page.rect.width * 0.45 else page.rect.width - 24.0

    labels: list[tuple[float, float, str]] = []
    for w in words:
        if w[0] < col_left - 1:
            continue
        if w[1] < carn_y1 - 2:
            continue
        t = w[4].strip()
        if re.match(r"^[A-C]\.$", t):
            labels.append((w[1], w[3], t[0]))

    labels.sort(key=lambda x: x[0])
    if len(labels) < 3:
        return None
    # First three A/B/C labels below the stem (this question's options)
    tail = labels[:3]
    if {x[2] for x in tail} != {"A", "B", "C"}:
        return None

    clips: list[fitz.Rect] = []
    for i, (y0, y1, _lab) in enumerate(tail):
        pad_t = 2.0
        pad_b = 6.0 if i < 2 else 14.0
        row_y0 = max(carn_y1 + 1, y0 - pad_t)
        row_y1 = min(page.rect.height - 8, y1 + pad_b)
        clips.append(fitz.Rect(col_left, row_y0, col_right, row_y1))
    return clips, col_right


def _fraction_count(s: str) -> int:
    return len(_FRACTION_LIKE.findall(s))


def _normalize_dental_ocr_line(s: str, row_label: str = "") -> str:
    s = s.strip()
    s = re.sub(r"^\|\s*", "", s)
    s = re.sub(r"^[A-D][.\)]\s*", "", s, flags=re.IGNORECASE)
    s = re.sub(r"\s*,\s*", ", ", s)
    s = re.sub(r",\s*,+", ", ", s)
    s = re.sub(r"\s+", " ", s)
    s = s.strip()
    # Tight glue: C1/ -> C 1/, pm4 -> pm 4, m2/ -> m 2/
    s = re.sub(r"\bC(\d)\s*/", r"C \1/", s)
    s = re.sub(r"\bI\s*(\d)\s*/", r"I \1/", s)
    s = re.sub(r"\bpm\s*(\d)", r"pm \1", s)
    s = re.sub(r",\s*m\s*(\d)", r", m \1", s)
    if row_label == "B":
        s = re.sub(r"^1%\s*,\s*CY\s*,", "I 0/2, C 1/1, ", s, flags=re.IGNORECASE)
    s = re.sub(r"^1%\s*", "I ", s)
    s = re.sub(r"^AL\s*", "I ", s, flags=re.IGNORECASE)
    # Stacked "0/3" often reads as "1%3" in these scans.
    s = re.sub(r"\b1%(\d)\b", r"0/\1", s)
    # "m 2/3" often glues as "m 27/" when the slash is faint.
    s = re.sub(r"\bm\s+27/", "m 2/3", s, flags=re.IGNORECASE)
    s = re.sub(r",\s*0\s*$", "", s)
    # Common JAMB dental-formula OCR fixes (stacked fractions + single-letter I).
    s = re.sub(r"\bC\s+1/\s*,\s*pm\b", "C 1/1, pm", s)
    s = re.sub(r"^12/(\d)", r"I 2/\1", s)
    s = re.sub(r"\bC\s+2/\s*,\s*pm\b", "C 2/1, pm", s)
    s = re.sub(r"\bpm\s+3/\s*,\s*m\b", "pm 3/4, m", s)
    if row_label == "B":
        s = re.sub(r"\bm\s+2/\s*,\s*$", "m 2/4", s)
    if row_label == "C":
        s = re.sub(r"\bm\s+2/\s*,\s*$", "m 2/3", s)
    return s.strip()


def _parse_ocr_options(ocr_text: str) -> Dict[str, str]:
    """Extract A./B./C./D. lines from OCR output."""
    out: Dict[str, str] = {}
    for line in ocr_text.splitlines():
        line = line.strip()
        if not line:
            continue
        m = re.match(r"^([A-D])[\.\)]\s*(.+)$", line, re.IGNORECASE)
        if m:
            out[m.group(1).upper()] = " ".join(m.group(2).split())
    return out


def _prep_ocr_image(img):
    """Grayscale + autocontrast + mild upscale for Tesseract on exam scans."""
    from PIL import Image, ImageOps  # type: ignore[import-untyped]

    g = img.convert("L")
    g = ImageOps.autocontrast(g, cutoff=1)
    w, h = g.size
    try:
        res = Image.Resampling.LANCZOS
    except AttributeError:
        res = Image.LANCZOS
    return g.resize((int(w * 1.25), int(h * 1.25)), res)


def _ocr_one_clip(page: "fitz.Page", clip, pytesseract, Image, row_label: str = "") -> str:
    import fitz

    mat = fitz.Matrix(_OCR_ZOOM, _OCR_ZOOM)
    pix = page.get_pixmap(matrix=mat, clip=clip, alpha=False, colorspace=fitz.csRGB)
    img = Image.open(io.BytesIO(pix.tobytes("png")))
    img = _prep_ocr_image(img)
    # Try two layouts: single-line vs raw; keep the read with more numeric fractions.
    cand7 = pytesseract.image_to_string(img, config="--oem 3 --psm 7").strip()
    cand13 = pytesseract.image_to_string(img, config="--oem 3 --psm 13").strip()
    if _fraction_count(cand13) > _fraction_count(cand7):
        raw = cand13
    else:
        raw = cand7
    return _normalize_dental_ocr_line(raw, row_label)


def _ocr_dental_option_rows(page: "fitz.Page") -> str:
    import fitz

    pytesseract, Image = _try_imports()
    if not pytesseract or not Image:
        return ""

    packed = _option_row_rects(page)
    if packed is None:
        return ""
    clips, _ = packed
    lines: list[str] = []
    for i, clip in enumerate(clips):
        if clip.is_empty:
            continue
        lab = ("A", "B", "C")[i] if i < 3 else "?"
        try:
            body = _ocr_one_clip(page, clip, pytesseract, Image, lab)
        except Exception as e:  # noqa: BLE001
            logger.warning("Tesseract OCR failed on row %s: %s", lab, e)
            continue
        if not body:
            continue
        body = re.sub(r"^[A-D][\.\)]\s*", "", body.strip(), flags=re.IGNORECASE)
        lines.append(f"{lab}. {body}")
    return "\n".join(lines)


def repair_vector_fraction_options(questions: List[dict], pdf_path: str) -> None:
    """
    In-place: for dental-formula questions with empty fractions in the text layer,
    OCR the option band and merge letter keys present in both OCR and the question.
    """
    pytesseract, _ = _try_imports()
    if not pytesseract:
        logger.debug("pytesseract not installed; skip math OCR repair")
        return

    import fitz

    try:
        doc = fitz.open(pdf_path)
    except Exception as e:  # noqa: BLE001
        logger.warning("Could not open PDF for OCR repair: %s", e)
        return

    try:
        for q in questions:
            if not _question_needs_dental_ocr(q):
                continue
            pidx = _find_page_index(doc, int(q["question_number"]), q["question"].lower())
            if pidx is None:
                continue
            page = doc[pidx]
            raw = _ocr_dental_option_rows(page)
            ocr_opts = _parse_ocr_options(raw)
            if len(ocr_opts) < 2:
                continue
            merged = dict(q["options"])
            replaced = False
            for letter, ocr_val in ocr_opts.items():
                if letter not in merged:
                    continue
                # At least one clear a/b fraction vs none in the PDF text layer.
                if _fraction_count(ocr_val) < 1:
                    continue
                merged[letter] = ocr_val
                replaced = True
            # Some papers only print A–C; a stray "D" can be an empty text-layer ghost.
            if replaced:
                dv = merged.get("D", "")
                if dv and _OPTION_HAS_TOOTH_LABELS.search(dv) and not _HAS_NUMERIC_FRACTION.search(dv):
                    del merged["D"]
            q["options"] = merged
    finally:
        doc.close()
