# Claideco

Independent software studio building back-office tools for Filipino bookkeepers, accountants, and SMBs.

This monorepo contains:

- `frontend/` — `claideco.work` public site and PesoBooks web app (Vue 3 + Vite).
- `backend/` — PesoBooks API (FastAPI + SQLAlchemy + PostgreSQL, Tesseract OCR, OpenAI extraction).
- `deploy/` — Nginx config, systemd service, and setup/redeploy scripts for Ubuntu 24.04 VPS.
- `PESOBOOKS_HANDOFF.md` — full implementation state, known gaps, and next-work checklist.

---

## PesoBooks

PesoBooks is bookkeeping infrastructure for Filipino accounting firms. Features:

- Bookkeeper signup with **email verification** + JWT login.
- Multi-client workspace with dashboard metrics.
- Batch receipt/invoice upload (JPEG, PNG, WebP, PDF).
- Image/PDF OCR and PH/BIR-aware OpenAI extraction.
- Review queue with editable extracted fields, confidence highlights, and Enter-to-approve shortcut.
- Receipt archive with filters (month, vendor, VAT type, amount range) and document detail modal.
- CSV export in Generic, QuickBooks, and Xero formats.
- Bank CSV import with PH bank presets (Generic, BDO, BPI, Metrobank, UnionBank).
- Duplicate-skipping bank import with row-level error reporting.
- Reconciliation match suggestions with 1%/2% withholding variance detection.
- Manual receipt search, undo/unmatch, and bulk transaction categorization.
- Form 2307 status tracking (missing → requested → received → attached) with file attachment workflow.

PDF files are rendered with PyMuPDF for OCR and in-app preview. File/preview endpoints use `Authorization: Bearer` headers — tokens never appear in URLs.

---

## Prerequisites

1. **Python 3.11+** (3.13 recommended).
2. **Node.js 20+**.
3. **PostgreSQL 14+**.
   - macOS: `brew install postgresql@16 && brew services start postgresql@16`
   - Linux: `sudo apt install postgresql`
   - Windows: EnterpriseDB installer.
   - Create a role and database:
     ```sql
     CREATE ROLE pesobooks WITH LOGIN PASSWORD 'pesobooks';
     CREATE DATABASE pesobooks OWNER pesobooks;
     ```
4. **Tesseract OCR**.
   - macOS: `brew install tesseract`
   - Linux: `sudo apt install tesseract-ocr`
   - Windows: UB-Mannheim builds; set `TESSERACT_CMD` env var if not on PATH.
5. **OpenAI API key** for field extraction.
6. **SMTP credentials** for verification emails. Gmail works with a [16-character App Password](https://support.google.com/accounts/answer/185833).
   > If `SMTP_HOST` is unset, the verification link is printed to the backend log — no email required for local dev.

---

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
API_KEY=<api-key>
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4o-mini
TESSERACT_CMD=
UPLOAD_DIR=./uploads
MAX_FILE_SIZE_MB=20
MAX_FILES_PER_UPLOAD=50

# PostgreSQL — required (SQLite and MySQL are not supported)
DATABASE_URL=postgresql+psycopg2://pesobooks:pesobooks@localhost:5432/pesobooks

# SMTP for verification emails
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=you@gmail.com
SMTP_PASSWORD=xxxx-xxxx-xxxx-xxxx
SMTP_FROM=you@gmail.com
SMTP_USE_TLS=true
FRONTEND_BASE_URL=http://localhost:5174
```

Run the backend:

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8001
```

API docs: `http://127.0.0.1:8001/docs`

---

## Frontend Setup

```powershell
cd frontend
npm install
$env:VITE_API_BASE_URL='http://127.0.0.1:8001/v1'
npm.cmd run dev -- --host 127.0.0.1 --port 5174
```

Visit `http://127.0.0.1:5174`

Key routes:

| Route | Description |
|---|---|
| `/` | Public home |
| `/signup` | Create account (sends verification email) |
| `/verify-email?token=...` | Email verification landing page |
| `/login` | Log in |
| `/app` | Dashboard |
| `/app/clients/new` | New client |
| `/app/clients/:id` | Client detail + upload |
| `/app/clients/:id/review` | Receipt review queue |
| `/app/clients/:id/archive` | Approved receipts + export |
| `/app/clients/:id/reconciliation` | Bank reconciliation + Form 2307 |

---

## VPS Deployment (Hostinger / Ubuntu 24.04)

All deployment files are in `deploy/`.

**First-time setup — run as root on the VPS:**

```bash
curl -o setup.sh https://raw.githubusercontent.com/kleyds/claideco.work/main/deploy/setup.sh
bash setup.sh
```

This installs all system dependencies, creates the PostgreSQL database, clones the repo, builds the frontend, issues an SSL certificate via Let's Encrypt, and starts the backend under systemd.

After setup, edit `/var/www/pesobooks-api/.env` to add `OPENAI_API_KEY` and SMTP credentials, then:

```bash
systemctl restart pesobooks
```

**Redeploy after a push:**

```bash
bash /path/to/claideco.work/deploy/redeploy.sh
```

Deployment stack: **Nginx** (reverse proxy + static file server) + **systemd** (uvicorn process manager) + **Let's Encrypt SSL**.

---

## Verification

Backend syntax check:

```powershell
cd backend
.\.venv\Scripts\python.exe -m compileall app
```

Frontend build check:

```powershell
cd frontend
npm.cmd run build
```

---

## API Reference

### Auth

| Method | Path | Description |
|---|---|---|
| POST | `/v1/auth/register` | Create account, send verification email |
| POST | `/v1/auth/verify-email` | Consume email token, return JWT |
| POST | `/v1/auth/resend-verification` | Re-send verification email |
| POST | `/v1/auth/login` | Login (rejects unverified accounts) |
| GET | `/v1/auth/me` | Current user |

### Clients

| Method | Path | Description |
|---|---|---|
| GET | `/v1/clients` | List clients |
| GET | `/v1/clients/metrics` | Dashboard counts |
| POST | `/v1/clients` | Create client |
| GET | `/v1/clients/{id}` | Client detail |
| PUT | `/v1/clients/{id}` | Update client |
| DELETE | `/v1/clients/{id}` | Soft-delete client |

### Receipts

| Method | Path | Description |
|---|---|---|
| POST | `/v1/clients/{id}/receipts/upload` | Batch upload |
| GET | `/v1/clients/{id}/receipts` | List receipts |
| GET | `/v1/clients/{id}/receipts/queue` | Review queue |
| GET | `/v1/receipts/{id}` | Receipt detail |
| PATCH | `/v1/receipts/{id}` | Update status/fields |
| POST | `/v1/receipts/{id}/reprocess` | Retry OCR |
| GET | `/v1/receipts/{id}/file` | Download file (Authorization header) |
| GET | `/v1/receipts/{id}/preview` | In-app preview (Authorization header) |
| GET | `/v1/clients/{id}/export` | CSV export (`?format=generic\|qbo\|xero`) |

### Bank & Reconciliation

| Method | Path | Description |
|---|---|---|
| POST | `/v1/clients/{id}/bank/import` | Import bank CSV (`?bank_template=generic\|bdo\|bpi\|metrobank\|unionbank`) |
| GET | `/v1/clients/{id}/bank/transactions` | Transaction list |
| GET | `/v1/clients/{id}/bank/transactions/{tx}/matches` | Match suggestions |
| GET | `/v1/clients/{id}/bank/transactions/{tx}/manual-matches` | Manual search (`?q=...`) |
| POST | `/v1/clients/{id}/bank/transactions/{tx}/reconcile` | Reconcile |
| GET | `/v1/clients/{id}/bank/reconciliations` | Reconciled list |
| DELETE | `/v1/clients/{id}/bank/reconciliations/{id}` | Undo match |
| PATCH | `/v1/clients/{id}/bank/transactions/category` | Bulk categorize |
| PATCH | `/v1/clients/{id}/bank/reconciliations/{id}/2307` | Update 2307 status/notes |
| POST | `/v1/clients/{id}/bank/reconciliations/{id}/2307/file` | Attach 2307 file |
| GET | `/v1/clients/{id}/bank/reconciliations/{id}/2307/file` | Download 2307 (Authorization header) |

---

## Next Work

See `PESOBOOKS_HANDOFF.md` for the full breakdown. High-priority items:

- Alembic migrations (currently using `create_all` + startup column patches).
- Receipt approval splice-before-confirm bug in `ClientReview.vue`.
- Archive pagination (currently loads all approved receipts in one request).
- Compliance exports: SLSP, SAWT, 4-column journal.
- Client portal upload links (no-login receipt submission).
