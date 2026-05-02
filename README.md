# Claideco

Independent software studio building back-office tools for Filipino bookkeepers, accountants, and SMBs.

This monorepo contains:

- `frontend/` - `claideco.work` site and PesoBooks web app.
- `backend/` - PesoBooks API built with FastAPI, SQLAlchemy, Tesseract OCR, and OpenAI extraction.
- `PESOBOOKS_HANDOFF.md` - implementation handoff and next-work checklist.

## PesoBooks

PesoBooks is bookkeeping infrastructure for Filipino accounting firms. It currently supports:

- Bookkeeper signup/login with JWT auth.
- Multi-client workspace.
- Batch receipt/invoice upload.
- Image OCR and PH/BIR-aware OpenAI extraction.
- Review queue with editable extracted fields.
- Receipt archive with filters.
- CSV export for Generic, QuickBooks, and Xero formats.
- Bank CSV import.
- Reconciliation match suggestions, including 1%/2% withholding variance detection.
- Bulk bank transaction categorization.

PDF files are stored, but PDF OCR/rendering is not implemented yet.

## Prerequisites

1. Python 3.13 recommended.
2. Node.js 20+.
3. Tesseract OCR.
   - Windows: install from UB-Mannheim builds and set `TESSERACT_CMD` if it is not on PATH.
   - macOS: `brew install tesseract`
   - Linux: `sudo apt install tesseract-ocr`
4. OpenAI API key for extraction.

## Backend Setup

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\activate
python -m pip install -r requirements.txt
copy .env.example .env
```

Edit `backend/.env`:

```text
APP_ENV=development
SECRET_KEY=<random 32-byte hex>
API_KEY=<legacy-api-key>
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4o-mini
TESSERACT_CMD=
UPLOAD_DIR=./uploads
MAX_FILE_SIZE_MB=20
MAX_FILES_PER_UPLOAD=50
DATABASE_URL=sqlite:///./pesobooks.db
```

For MySQL, set:

```text
DATABASE_URL=mysql+pymysql://user:pass@localhost:3306/pesobooks
```

Run the backend:

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8001
```

API docs:

```text
http://127.0.0.1:8001/docs
```

## Frontend Setup

```powershell
cd frontend
npm install
$env:VITE_API_BASE_URL='http://127.0.0.1:8001/v1'
npm.cmd run dev -- --host 127.0.0.1 --port 5174
```

Visit:

```text
http://127.0.0.1:5174
```

Key routes:

- `/`
- `/products`
- `/pesobooks`
- `/docs`
- `/login`
- `/signup`
- `/app`
- `/app/clients/new`
- `/app/clients/:id`
- `/app/clients/:id/review`
- `/app/clients/:id/archive`
- `/app/clients/:id/reconciliation`

## Verification

Backend:

```powershell
cd backend
.\.venv\Scripts\python.exe -m compileall app
```

Frontend:

```powershell
cd frontend
npm.cmd run build
```

## Important API Areas

Auth:

- `POST /v1/auth/register`
- `POST /v1/auth/login`
- `GET /v1/auth/me`

Clients:

- `GET /v1/clients`
- `POST /v1/clients`
- `GET /v1/clients/{id}`
- `PUT /v1/clients/{id}`
- `DELETE /v1/clients/{id}`

Receipts:

- `POST /v1/clients/{id}/receipts/upload`
- `GET /v1/clients/{id}/receipts`
- `GET /v1/clients/{id}/receipts/queue`
- `GET /v1/receipts/{id}`
- `GET /v1/receipts/{id}/file?token=...`
- `PATCH /v1/receipts/{id}`

Exports:

- `GET /v1/clients/{id}/export?format=generic|qbo|xero`

Bank/reconciliation:

- `POST /v1/clients/{id}/bank/import`
- `GET /v1/clients/{id}/bank/transactions`
- `GET /v1/clients/{id}/bank/transactions/{tx_id}/matches`
- `POST /v1/clients/{id}/bank/transactions/{tx_id}/reconcile`
- `PATCH /v1/clients/{id}/bank/transactions/category`

Legacy endpoint:

- `POST /v1/extract-receipt`

## Next Work

See `PESOBOOKS_HANDOFF.md` for the fuller handoff. High-priority next slices:

- Form 2307 tracking UI and backend fields.
- Reconciled transactions view and undo/unmatch.
- PDF OCR/rendering support.
- Receipt archive read-only detail view.
- Dashboard metrics.
- Alembic migrations.
- Docker deployment setup.
