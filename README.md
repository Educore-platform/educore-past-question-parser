# educore-past-question-parser

A FastAPI service for extracting and structuring past questions from JAMB/WAEC PDF files.

## Setup

```bash
pip install -r requirements.txt
```

Start MongoDB (local example):

```bash
# Docker
docker run -d -p 27017:27017 --name mongo mongo:7
```

Environment (optional; defaults shown):

| Variable | Default | Purpose |
|----------|---------|---------|
| `MONGODB_URI` | `mongodb://localhost:27017` | MongoDB connection string |
| `MONGODB_DB` | `educore` | Database name |

## Run

```bash
uvicorn app.main:app --reload
```

Server starts at: http://localhost:8000

- **Swagger UI** (try uploads in the browser): http://localhost:8000/docs  
- **ReDoc**: http://localhost:8000/redoc  
- **OpenAPI JSON**: http://localhost:8000/openapi.json  

PDFs are written to `data/uploads/` (see `app/services/file_service.py`).

## Layout

- `app/main.py` — FastAPI app, OpenAPI metadata, router mount  
- `app/api/v1/` — Versioned routes (`/api/v1/...`)  
- `app/services/file_service.py` — Save uploads under the project path  
- `app/services/pdf_parser.py` — PyMuPDF text extraction and JAMB-style parsing  
- `app/schemas/` — Pydantic models used in Swagger response schemas  
- `app/models/question.py` — Beanie `QuestionDocument` (collection `questions`, indexes)  
- `app/db/lifespan.py` — MongoDB client + Beanie init on startup  

## Endpoints (v1)

### POST /api/v1/extract/questions
Upload a PDF, parse and **save each question to MongoDB** as one PDF upload. The JSON body is wrapped in `{ success, error, data, message }`; `data` is a summary (`filename`, `total_pages`, `years_detected`, `total_questions`, `persisted_count`, `file_id`, `subject_code`, `subject_name`, etc.) — not the full question list. Use `GET /api/v1/questions?file_id=…` or `?subject_code=…` (with `subject`) to read what was stored.

Example stored question shape (as returned by GET):
```json
{
  "year": "2010",
  "subject": "Government",
  "exam": "JAMB",
  "question_number": 2,
  "question": "Nation-state is synonymous with ----",
  "options": {
    "A": "self-actualization",
    "B": "sovereignty",
    "C": "liberation",
    "D": "nationalism"
  },
  "answer": "B",
  "explanation": null
}
```

### GET /api/v1/questions
List stored questions with optional filters: `year`, `subject`, `exam`, `question_number`, `file_id`, `subject_code`, `search` (substring on stem), plus `skip` / `limit` (max 200). Sorted by `created_at` descending.

### GET /api/v1/questions/imports
Lists distinct PDF uploads (grouped by `file_id`) with counts and metadata — useful for picking a past paper upload in the UI.

### GET /api/v1/questions/{question_id}
Fetch a single question by MongoDB ObjectId (hex string).

## Supported PDF Types
- JAMB past questions (multi-year PDFs)
- Single year PDFs
- Digital PDFs (not scanned)

## Notes
- Scanned PDFs require OCR — that will be a separate service
- The parser handles the standard JAMB MCQ format
- Explanations field is null by default — can be filled later via AI
# educore-past-question-parser
