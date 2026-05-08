# PesoBooks Handoff

## Current State

Stack:
- Frontend: Vue 3 + Vite, running on `http://127.0.0.1:5174`
- Backend: FastAPI + SQLAlchemy, running on `http://127.0.0.1:8001`
- Database: **PostgreSQL** (SQLite removed; MySQL removed)
- Auth: JWT + bcrypt, email verification required before login
- File storage: local disk under `backend/uploads/`
- File previews: served via Authorization header (no token in URL)
- Deployment: Nginx + systemd on Ubuntu 24.04 VPS (see `deploy/`)

---

## Implemented

### Public/Product
- Claideco public pages
- PesoBooks product page aligned to PRD
- API docs page

### Auth
- Signup with **email verification flow**:
  - `POST /v1/auth/register` — creates user, sends verification email, returns message (no token)
  - `POST /v1/auth/verify-email` — consumes token from email link, returns JWT
  - `POST /v1/auth/resend-verification` — 60s cooldown, generic response (prevents email enumeration)
  - `POST /v1/auth/login` — rejects unverified users with 403
  - `GET /v1/auth/me`
- SMTP email delivery via `email_service.py` (configurable via env vars)
- If `SMTP_HOST` is unset, verification link is printed to the backend log (local dev fallback)
- JWT stored in `localStorage`, protected `/app` routes
- Frontend flows:
  - `Signup.vue` — shows "check your email" state + resend button after registration
  - `Login.vue` — detects unverified error and surfaces resend button
  - `VerifyEmail.vue` — `/verify-email?token=...` route handles the email link, auto-redirects to `/app`

### Client Workspace
- `Client` model
- Client CRUD API:
  - `GET /v1/clients`
  - `POST /v1/clients`
  - `GET /v1/clients/{id}`
  - `PUT /v1/clients/{id}`
  - `DELETE /v1/clients/{id}`
- Client metrics API:
  - `GET /v1/clients/metrics`
- Client dashboard
- Create client page
- Client detail page
- Dashboard cards show real counts for unprocessed invoices, unreconciled bank entries, missing/outstanding 2307s, and total open work
- App header switches from public Claideco navigation to PesoBooks navigation on `/app` routes
- Client detail metadata is collapsed by default so upload and workflow actions stay above the fold

### Receipt/Invoice Workflow
- Receipt models: `receipts`, `receipt_data`, `line_items`
- Batch upload:
  - `POST /v1/clients/{id}/receipts/upload`
- Receipt list/detail:
  - `GET /v1/clients/{id}/receipts`
  - `GET /v1/receipts/{id}`
- Receipt reprocess/retry:
  - `POST /v1/receipts/{id}/reprocess`
- Protected file access (Authorization header only — no token in URL):
  - `GET /v1/receipts/{id}/file`
  - `GET /v1/receipts/{id}/preview`
- Frontend fetches previews via `apiFetchBlob` + `URL.createObjectURL()` so tokens never appear in browser history or server logs
- OCR/OpenAI extraction for image and PDF files
- PDFs rendered with PyMuPDF for OCR and in-app preview
- PH/BIR extraction fields: vendor TIN, OR/SI number, VAT type, VATable amount, VAT amount, document type, confidence

### Review Queue
- `GET /v1/clients/{id}/receipts/queue`
- `PATCH /v1/receipts/{id}`
- `/app/clients/:id/review`
- Side-by-side document and editable fields
- Approve/reject flow
- Retry OCR action for failed receipts
- Confidence highlighting
- Enter-to-approve keyboard shortcut
- `onUnmounted` keydown listener cleanup (memory leak fixed)
- Preview blob URL revoked on unmount and on receipt change (stale-request guard added)
- Review page uses a fixed-height workbench layout on desktop
- Empty review queue shows "You're all caught up" state with upload/archive actions

### Archive/Export
- `/app/clients/:id/archive`
- Filter approved receipts by: month, vendor, document type, VAT type, amount range
- CSV export:
  - `GET /v1/clients/{id}/export`
  - formats: `generic`, `qbo`, `xero`
- Archive detail modal with app-rendered image/PDF preview, zoom controls, extracted BIR fields, line items, raw OCR text
- Preview loaded via blob fetch (same Authorization-header pattern as review queue)
- `onUnmounted` cleanup for event listeners and blob URLs

### Bank Reconciliation
- Models: `bank_transactions`, `reconciliations`
- Bank CSV import:
  - `POST /v1/clients/{id}/bank/import`
- Bank CSV template presets: Generic, BDO, BPI, Metrobank, UnionBank
- Bank import skips likely duplicate rows, returns row-level parse errors
- Bank transaction list:
  - `GET /v1/clients/{id}/bank/transactions`
- Match suggestions:
  - `GET /v1/clients/{id}/bank/transactions/{tx_id}/matches`
- Match logic: exact amount, 1%/2% withholding variance, date within 7 days, vendor similarity
- Reconcile action:
  - `POST /v1/clients/{id}/bank/transactions/{tx_id}/reconcile`
- Reconciled transaction list:
  - `GET /v1/clients/{id}/bank/reconciliations`
- Manual receipt match search:
  - `GET /v1/clients/{id}/bank/transactions/{tx_id}/manual-matches?q=...`
- Undo/unmatch:
  - `DELETE /v1/clients/{id}/bank/reconciliations/{reconciliation_id}`
- Bulk categorization:
  - `PATCH /v1/clients/{id}/bank/transactions/category`

### Form 2307 Tracking
- Reconciliation-level 2307 status: `missing`, `requested`, `received`, `attached`
- Metadata: requested/received/uploaded timestamps, follow-up notes
- 2307 APIs:
  - `GET /v1/clients/{id}/bank/reconciliations?requires_2307=true`
  - `PATCH /v1/clients/{id}/bank/reconciliations/{reconciliation_id}/2307`
  - `POST /v1/clients/{id}/bank/reconciliations/{reconciliation_id}/2307/file`
  - `GET /v1/clients/{id}/bank/reconciliations/{reconciliation_id}/2307/file` (Authorization header)
- 2307 file open in frontend uses blob fetch + `window.open(blobUrl)` — no token in URL
- Lightweight startup migration adds 2307 columns to existing `reconciliations` tables

### Database
- **PostgreSQL** via `psycopg2-binary`
- Connection pooling: `pool_size`, `max_overflow`, `pool_recycle`, `pool_pre_ping` — all configurable via env
- Startup lightweight migrations: identifier-whitelist validated before any DDL (no f-string SQL)
- `User` model gains `is_verified`, `verification_token`, `verification_token_expires_at`, `verification_sent_at`

### VPS Deployment (`deploy/`)
- `nginx.conf` — reverse proxies `/v1/` to FastAPI, serves Vue SPA with history-mode fallback, gzip + cache headers, 25 MB upload limit, SSL via Let's Encrypt
- `pesobooks.service` — systemd unit running uvicorn as `www-data`, auto-restarts on crash/reboot
- `setup.sh` — full first-run script: installs all deps, creates Postgres DB with random password, clones repo, builds frontend, issues SSL cert, enables systemd service
- `redeploy.sh` — pulls latest, rebuilds frontend, reinstalls Python deps, restarts service

---

## Important Files

Backend:
- `backend/app/main.py`
- `backend/app/database.py`
- `backend/app/models.py`
- `backend/app/auth.py`
- `backend/app/auth_routes.py`
- `backend/app/email_service.py` ← new
- `backend/app/client_routes.py`
- `backend/app/receipt_routes.py`
- `backend/app/bank_routes.py`
- `backend/app/schemas.py`
- `backend/app/extract.py`
- `backend/app/ocr.py`

Frontend:
- `frontend/src/api.js` (includes `apiFetchBlob`, `loadAuthorizedObjectUrl`)
- `frontend/src/main.js`
- `frontend/src/views/Login.vue`
- `frontend/src/views/Signup.vue`
- `frontend/src/views/VerifyEmail.vue` ← new
- `frontend/src/views/AppDashboard.vue`
- `frontend/src/views/ClientNew.vue`
- `frontend/src/views/ClientDetail.vue`
- `frontend/src/views/ClientReview.vue`
- `frontend/src/views/ClientArchive.vue`
- `frontend/src/views/ClientReconciliation.vue`

Deployment:
- `deploy/nginx.conf`
- `deploy/pesobooks.service`
- `deploy/setup.sh`
- `deploy/redeploy.sh`

---

## Known Gaps / Needs Completion

High priority:
- **Alembic migrations** — startup `create_all` + lightweight column migration still in place; needs proper Alembic setup for production schema changes
- **Automated tests** — no regression tests for reconciliation, 2307 tracking, PDF OCR, dashboard metrics, or the verification flow
- **Receipt approval splice bug** — in `ClientReview.vue`, the receipt is removed from the queue before the PATCH succeeds; if the API call fails, the receipt disappears from view
- **No confirmation before reject** — destructive action with no undo in the review queue
- **No archive pagination** — all approved receipts load in one request; will be slow at scale

Medium priority:
- `requires_2307` stored as `"true"/"false"` string in `Reconciliation` model — should be `bool`
- `_client_or_404` duplicated in `bank_routes.py` and `receipt_routes.py` — extract to shared `deps.py`
- No debounce on manual reconciliation search input
- No retry logic in `process_receipt` background task for transient OCR/file failures

---

## Recommended Next Product Slices

1. **Compliance exports**
   - SLSP/SAWT export
   - 4-column journal export
   - BIR deadline flags

2. **Client portal**
   - Public upload links (no login required)
   - Query/clarification flow
   - Mobile-first upload page

3. **Billing/limits**
   - Receipt limits per plan
   - PayMongo integration
   - Billing status/settings page

4. **Production hardening**
   - Alembic migrations
   - Rate limiting on import/matching/OCR endpoints
   - Archive pagination
   - Fix receipt approval splice-before-confirm bug

---

## Current Test Commands

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

## Current Dev Servers

```text
Backend:  http://127.0.0.1:8001
Frontend: http://127.0.0.1:5174
```

Frontend must be started with:

```powershell
$env:VITE_API_BASE_URL='http://127.0.0.1:8001/v1'
npm.cmd run dev -- --host 127.0.0.1 --port 5174
```
