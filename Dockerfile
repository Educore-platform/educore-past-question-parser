# ── Stage 1: Builder ─────────────────────────────────────────────────────────
# Install build-time tools and compile all Python packages with C extensions.
FROM python:3.13-alpine AS builder

WORKDIR /build

# gcc + musl-dev: required to compile hiredis and other C-extension packages.
# libffi-dev: needed by some transitive dependencies.
RUN apk add --no-cache \
    gcc \
    musl-dev \
    python3-dev \
    libffi-dev

COPY requirements.txt .

# Install into /install so the final stage only needs to copy this prefix.
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt


# ── Stage 2: Runtime ─────────────────────────────────────────────────────────
FROM python:3.13-alpine

WORKDIR /app

# tesseract-ocr:          OCR engine required by pytesseract.
# tesseract-ocr-data-eng: English language data pack.
# libstdc++:              C++ runtime needed by PyMuPDF's musllinux wheel.
# libgomp:                OpenMP runtime used by some image-processing paths.
RUN apk add --no-cache \
    tesseract-ocr \
    tesseract-ocr-data-eng \
    libstdc++ \
    libgomp

# Pull in the compiled packages from the builder stage.
COPY --from=builder /install /usr/local

# Pre-create the data directories; mount these as volumes in production so
# uploaded PDFs and extracted images survive container restarts.
RUN mkdir -p data/uploads data/images

COPY app/ app/
COPY main.py .

# Run as a non-root user.
RUN adduser -D -H -s /sbin/nologin appuser \
    && chown -R appuser:appuser /app

USER appuser

EXPOSE 8000

# Override WEB_CONCURRENCY to run multiple uvicorn workers (default: 1).
CMD ["sh", "-c", \
     "uvicorn app.main:app \
      --host 0.0.0.0 \
      --port ${PORT:-8000} \
      --workers ${WEB_CONCURRENCY:-1} \
      --log-level ${LOG_LEVEL:-info}"]
