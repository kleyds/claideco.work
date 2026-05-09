# Claideco

Independent software studio building back-office tools for Filipino bookkeepers, accountants, and SMBs.

This monorepo contains:

- `frontend/` - `claideco.work` site and PesoBooks web app.
- `backend/` - PesoBooks API built with FastAPI, SQLAlchemy on PostgreSQL, Tesseract OCR, and OpenAI extraction.
- `PESOBOOKS_HANDOFF.md` - implementation handoff and next-work checklist.

## PesoBooks

PesoBooks is bookkeeping infrastructure for Filipino accounting firms. It currently supports:

- Bookkeeper signup with email verification + JWT login.
- Multi-client workspace.
- Batch receipt/invoice upload.
- Image/PDF OCR and PH/BIR-aware OpenAI extraction.
- Review queue with editable extracted fields.
- Receipt archive with filters and read-only modal document detail.
- CSV export for Generic, QuickBooks, and Xero formats.
- Bank CSV import.
- PH bank CSV template presets for Generic, BDO, BPI, Metrobank, and UnionBank imports.
- Bank import duplicate skipping and row-level error reporting.
- Reconciliation match suggestions, including 1%/2% withholding variance detection.
- Reconciled transaction view with undo/unmatch and manual receipt search.
- Form 2307 status tracking and attachment workflow.
- Dashboard metrics for unprocessed invoices, unreconciled bank entries, and missing 2307s.
- Bulk bank transaction categorization.
- BIR compliance exports: SLSP, SAWT, 4-column journal, upcoming deadlines.
- Client portal: tokenized public upload links, mobile-first upload page, expiry/limit/revoke controls.

PDF files are stored, previewed in-app as rendered page images, and OCRed by rendering pages with PyMuPDF.

## Prerequisites

1. Python 3.13 recommended.
2. Node.js 20+.
3. PostgreSQL 14+ running locally (or any reachable Postgres instance).
   - macOS: `brew install postgresql@16 && brew services start postgresql@16`
   - Linux: `sudo apt install postgresql`
   - Windows: install via the EnterpriseDB installer.
   - Create a database and role, e.g.:
     ```sql
     CREATE ROLE pesobooks WITH LOGIN PASSWORD 'pesobooks';
     CREATE DATABASE pesobooks OWNER pesobooks;
     ```
4. Tesseract OCR.
   - Windows: install from UB-Mannheim builds and set `TESSERACT_CMD` if it is not on PATH.
   - macOS: `brew install tesseract`
   - Linux: `sudo apt install tesseract-ocr`
5. OpenAI API key for extraction.
6. SMTP credentials for sending verification emails (Gmail, SendGrid, Mailgun, etc.). For Gmail, use an [app password](https://support.google.com/accounts/answer/185833) and set `SMTP_HOST=smtp.gmail.com`, `SMTP_PORT=587`.
7. PyMuPDF is installed from `backend/requirements.txt` for PDF OCR; no Poppler install is required.

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

# PostgreSQL is required.
DATABASE_URL=postgresql+psycopg2://pesobooks:pesobooks@localhost:5432/pesobooks

# SMTP for verification emails. With Gmail, SMTP_USER is your address
# and SMTP_PASSWORD is a 16-character Google App Password.
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=you@gmail.com
SMTP_PASSWORD=xxxx-xxxx-xxxx-xxxx
SMTP_FROM=you@gmail.com
SMTP_USE_TLS=true
FRONTEND_BASE_URL=http://localhost:5174
```

> PostgreSQL is required. The backend uses `psycopg2-binary`; provision Postgres
> before starting the backend and set `DATABASE_URL` accordingly:
>
> ```text
> DATABASE_URL=postgresql+psycopg2://user:pass@localhost:5432/pesobooks
> ```

> If `SMTP_HOST` is unset, registration still succeeds and the verification link is
> printed to the backend log so you can verify accounts during local development.

Run database migrations (also runs automatically on app startup):

```powershell
.\.venv\Scripts\python.exe -m alembic upgrade head
```

To create a new migration after editing `app/models.py`:

```powershell
.\.venv\Scripts\python.exe -m alembic revision --autogenerate -m "describe change"
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
- `/app/clients/:id/compliance`
- `/portal/:token` (public client upload page)

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

- `POST /v1/auth/register` (sends verification email; does not return a token)
- `POST /v1/auth/verify-email` (consumes the token from the email and returns an access token)
- `POST /v1/auth/resend-verification`
- `POST /v1/auth/login` (rejects unverified users)
- `GET /v1/auth/me`

Clients:

- `GET /v1/clients`
- `GET /v1/clients/metrics`
- `POST /v1/clients`
- `GET /v1/clients/{id}`
- `PUT /v1/clients/{id}`
- `DELETE /v1/clients/{id}`

Receipts:

- `POST /v1/clients/{id}/receipts/upload`
- `GET /v1/clients/{id}/receipts`
- `GET /v1/clients/{id}/receipts/queue`
- `GET /v1/receipts/{id}`
- `POST /v1/receipts/{id}/reprocess`
- `GET /v1/receipts/{id}/file` (Authorization header)
- `GET /v1/receipts/{id}/preview` (Authorization header)
- `PATCH /v1/receipts/{id}`

Exports:

- `GET /v1/clients/{id}/export?format=generic|qbo|xero`
- `GET /v1/clients/{id}/exports/slsp?quarter=YYYY-Qn`
- `GET /v1/clients/{id}/exports/sawt?quarter=YYYY-Qn`
- `GET /v1/clients/{id}/exports/journal?month=YYYY-MM`
- `GET /v1/clients/{id}/compliance/deadlines`

Client portal:

- `POST /v1/clients/{id}/upload-links`
- `GET /v1/clients/{id}/upload-links`
- `DELETE /v1/clients/{id}/upload-links/{link_id}`
- `GET /v1/portal/{token}` (public)
- `POST /v1/portal/{token}/upload` (public)

Bank/reconciliation:

- `POST /v1/clients/{id}/bank/import?bank_template=generic|bdo|bpi|metrobank|unionbank`
- `GET /v1/clients/{id}/bank/transactions`
- `GET /v1/clients/{id}/bank/transactions/{tx_id}/matches`
- `GET /v1/clients/{id}/bank/transactions/{tx_id}/manual-matches?q=...`
- `POST /v1/clients/{id}/bank/transactions/{tx_id}/reconcile`
- `GET /v1/clients/{id}/bank/reconciliations`
- `DELETE /v1/clients/{id}/bank/reconciliations/{reconciliation_id}`
- `GET /v1/clients/{id}/bank/reconciliations?requires_2307=true`
- `PATCH /v1/clients/{id}/bank/reconciliations/{reconciliation_id}/2307`
- `POST /v1/clients/{id}/bank/reconciliations/{reconciliation_id}/2307/file`
- `GET /v1/clients/{id}/bank/reconciliations/{reconciliation_id}/2307/file` (Authorization header)
- `PATCH /v1/clients/{id}/bank/transactions/category`

Legacy endpoint:

- `POST /v1/extract-receipt`

## Next Work

See `PESOBOOKS_HANDOFF.md` for the fuller handoff. High-priority next slices:

- Client portal clarification/comments flow on top of existing public upload links.
- Docker deployment setup.
