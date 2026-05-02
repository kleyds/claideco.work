# Claideco

Independent software studio building back-office tools for Filipino bookkeepers, accountants, and SMBs.

This monorepo contains:

- **`frontend/`** — `claideco.work` site: studio homepage + product pages (PesoBooks at `/pesobooks`).
- **`backend/`** — PesoBooks API (FastAPI + Tesseract + OpenAI). Receipt → structured JSON.

## Products

- **PesoBooks** (`/pesobooks`) — bookkeeping infrastructure for Filipino accounting firms. Currently in private beta.

## Prerequisites

1. **Python 3.11+** (you have 3.13).
2. **Node.js 20+** (you have 22).
3. **Tesseract OCR**:
   - **Windows**: install from [UB-Mannheim builds](https://github.com/UB-Mannheim/tesseract/wiki). Either add to PATH, or set `TESSERACT_CMD` in `backend/.env` to the full path (e.g. `C:\Program Files\Tesseract-OCR\tesseract.exe`).
   - **macOS**: `brew install tesseract`
   - **Linux**: `sudo apt install tesseract-ocr`
4. **OpenAI API key** — https://platform.openai.com/api-keys

## Backend setup

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate          # Windows (Git Bash: source .venv/Scripts/activate)
# source .venv/bin/activate     # macOS/Linux

pip install -r requirements.txt

cp .env.example .env
# Edit .env:
#   API_KEY=<any random string>
#   OPENAI_API_KEY=sk-...
#   TESSERACT_CMD=<full path to tesseract.exe on Windows, leave blank elsewhere>

uvicorn app.main:app --reload --port 8000
```

Swagger UI at http://localhost:8000/docs.

### Test the endpoint

```bash
curl -X POST http://localhost:8000/v1/extract-receipt \
  -H "x-api-key: <your-API_KEY-from-.env>" \
  -F "file=@path/to/receipt.jpg"
```

## Frontend setup

```bash
cd frontend
npm install
npm run dev
```

Visit http://localhost:5173. Routes: `/`, `/products`, `/pesobooks`, `/docs`, `/about`.

## v0 architecture

```
Browser (claideco.work + /pesobooks app) ──┐
                                           │     ┌──────────────────────────────┐
                                           ├───► │  FastAPI                     │
                              curl ────────┘     │   POST /v1/extract-receipt   │
                                                 │     ├─ Tesseract (OCR)       │
                                                 │     └─ OpenAI (extract JSON) │
                                                 └──────────────────────────────┘
```

Sync request/response. No queue, no DB, no user accounts — those go in once one workflow is real.

## Roadmap (PesoBooks)

- [ ] Bookkeeper signup + auth (MySQL).
- [ ] Multi-client workspace.
- [ ] Web upload UI: drag-drop, batch, review queue.
- [ ] Free client portal for SMB clients of paying bookkeepers.
- [ ] BIR-aware extraction (TIN, OR/SI #, ATP, VAT-able vs zero-rated).
- [ ] PDF support (poppler) — needed for bank statements.
- [ ] GCash/Maya/BPI/BDO/Metrobank statement parsers.
- [ ] Direct exports: QuickBooks Online, Xero, JuanTax, CSV.
- [ ] Async job queue (Redis + RQ) once batches get large.
- [ ] Per-seat billing (peso-denominated).
