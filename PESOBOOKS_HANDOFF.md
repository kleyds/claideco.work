# PesoBooks Handoff

## Current State

Stack:
- Frontend: Vue 3 + Vite, running on `http://127.0.0.1:5174`
- Backend: FastAPI + SQLAlchemy, running on `http://127.0.0.1:8001`
- Local DB fallback: SQLite via `DATABASE_URL`, MySQL-compatible SQLAlchemy setup
- Auth: JWT + bcrypt
- File storage: local disk under `backend/uploads/`

## Implemented

### Public/Product
- Claideco public pages
- PesoBooks product page aligned to PRD
- API docs page

### Auth
- Signup/login frontend
- `POST /v1/auth/register`
- `POST /v1/auth/login`
- `GET /v1/auth/me`
- JWT stored in `localStorage`
- Protected `/app` routes

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
- Protected file access:
  - `GET /v1/receipts/{id}/file?token=...`
- Protected image/PDF preview:
  - `GET /v1/receipts/{id}/preview?token=...`
- OCR/OpenAI extraction for image and PDF files
- PDFs are rendered with PyMuPDF for OCR and previewed in-app through the protected preview route
- PH/BIR extraction fields:
  - vendor TIN
  - OR/SI number
  - VAT type
  - VATable amount
  - VAT amount
  - document type
  - confidence

### Review Queue
- `GET /v1/clients/{id}/receipts/queue`
- `PATCH /v1/receipts/{id}`
- `/app/clients/:id/review`
- Side-by-side document and editable fields
- Approve/reject flow
- Retry OCR action for failed receipts
- Confidence highlighting
- Enter-to-approve shortcut
- Review page uses a fixed-height workbench layout on desktop
- Queue, document/PDF preview, and extracted-field panes scroll independently with scroll chaining contained
- PDF receipts preview as app-rendered page images so the native browser PDF download toolbar is not shown; image receipts keep app-level zoom controls
- Document previews are anchored to the top center so zoomed-out PDFs do not float below blank space
- Review queue cards clamp long file names so PDF names do not overflow the sidebar
- Empty review queue shows an "You're all caught up" state with upload/archive actions

### Archive/Export
- `/app/clients/:id/archive`
- Filter approved receipts by:
  - month
  - vendor
  - document type
  - VAT type
  - amount range
- CSV export:
  - `GET /v1/clients/{id}/export`
  - formats: `generic`, `qbo`, `xero`
- Archive read-only detail modal:
  - app-rendered image/PDF preview
  - zoom controls
  - fixed popup header with internal detail scrolling
  - extracted BIR fields
  - line items
  - raw OCR text
- Protected receipt previews are served through app-rendered image/PDF page previews; 2307 file responses are served inline for browser preview

### Bank Reconciliation
- Models:
  - `bank_transactions`
  - `reconciliations`
- Bank CSV import:
  - `POST /v1/clients/{id}/bank/import`
- Bank CSV template presets:
  - Generic
  - BDO
  - BPI
  - Metrobank
  - UnionBank
- Bank import skips likely duplicate rows and returns row-level parse errors for bad amount rows
- Bank transaction list:
  - `GET /v1/clients/{id}/bank/transactions`
- Match suggestions:
  - `GET /v1/clients/{id}/bank/transactions/{tx_id}/matches`
- Match logic:
  - exact amount
  - 1%/2% withholding variance
  - date within 7 days
  - vendor similarity
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
- `/app/clients/:id/reconciliation` includes unreconciled entries, suggested matches, manual search, reconciled entries, undo match, and Form 2307 follow-up

### Form 2307 Tracking
- Reconciliation-level 2307 status fields:
  - `missing`
  - `requested`
  - `received`
  - `attached`
- Reconciliation-level 2307 workflow metadata:
  - requested timestamp
  - received timestamp
  - attachment upload timestamp
  - follow-up notes
- Lightweight startup schema upgrade adds 2307 columns to existing `reconciliations` tables until Alembic exists
- 2307 follow-up APIs:
  - `GET /v1/clients/{id}/bank/reconciliations?requires_2307=true`
  - `GET /v1/clients/{id}/bank/reconciliations?requires_2307=true&form_2307_status=requested`
  - `PATCH /v1/clients/{id}/bank/reconciliations/{reconciliation_id}/2307` for status and notes
  - `POST /v1/clients/{id}/bank/reconciliations/{reconciliation_id}/2307/file`
  - `GET /v1/clients/{id}/bank/reconciliations/{reconciliation_id}/2307/file?token=...`
- Status transitions automatically stamp requested/received dates, and `attached` requires a file upload
- `/app/clients/:id/reconciliation` now includes a Form 2307 follow-up panel for withholding-variance matches, status filtering, timestamps, notes, and attachment links
- 2307 attachments are stored locally under the upload root and support PDF/JPEG/PNG/WebP

## Important Files

Backend:
- `backend/app/main.py`
- `backend/app/database.py`
- `backend/app/models.py`
- `backend/app/auth.py`
- `backend/app/auth_routes.py`
- `backend/app/client_routes.py`
- `backend/app/receipt_routes.py`
- `backend/app/bank_routes.py`
- `backend/app/schemas.py`
- `backend/app/extract.py`
- `backend/app/ocr.py`

Frontend:
- `frontend/src/api.js`
- `frontend/src/main.js`
- `frontend/src/views/Login.vue`
- `frontend/src/views/Signup.vue`
- `frontend/src/views/AppDashboard.vue`
- `frontend/src/views/ClientNew.vue`
- `frontend/src/views/ClientDetail.vue`
- `frontend/src/views/ClientReview.vue`
- `frontend/src/views/ClientArchive.vue`
- `frontend/src/views/ClientReconciliation.vue`

## Known Gaps / Needs Completion

High priority:
- Better migrations: currently using `Base.metadata.create_all`, no Alembic
- MySQL production validation
- Automated regression tests for reconciliation, 2307 tracking, PDF OCR, and dashboard metrics

## Recommended Next Product Slices

1. Compliance exports
   - SLSP/SAWT export
   - 4-column journal export
   - BIR deadline flags

2. Client portal
   - Public upload links
   - Query/clarification flow
   - Mobile-first upload page

3. Billing/limits
   - Receipt limits per plan
   - Paymongo integration
   - Billing status/settings page

4. Deployment
   - Dockerfile/backend
   - Dockerfile/frontend or static build
   - docker-compose with DB
   - environment docs
   - production CORS/secret handling

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
