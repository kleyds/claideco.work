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
- Client dashboard
- Create client page
- Client detail page

### Receipt/Invoice Workflow
- Receipt models: `receipts`, `receipt_data`, `line_items`
- Batch upload:
  - `POST /v1/clients/{id}/receipts/upload`
- Receipt list/detail:
  - `GET /v1/clients/{id}/receipts`
  - `GET /v1/receipts/{id}`
- Protected file access:
  - `GET /v1/receipts/{id}/file?token=...`
- OCR/OpenAI extraction for image files
- PDFs are stored but not OCR-rendered yet
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
- Confidence highlighting
- Enter-to-approve shortcut

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

### Bank Reconciliation
- Models:
  - `bank_transactions`
  - `reconciliations`
- Bank CSV import:
  - `POST /v1/clients/{id}/bank/import`
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
- Bulk categorization:
  - `PATCH /v1/clients/{id}/bank/transactions/category`
- `/app/clients/:id/reconciliation`

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
- PDF OCR/rendering support
- Form 2307 tracking UI and backend fields
- Reconciled transactions view
- Ability to undo/unmatch reconciliations
- Receipt archive read-only detail view
- Dashboard metrics:
  - unprocessed invoices
  - unreconciled bank entries
  - missing 2307s
- Better migrations: currently using `Base.metadata.create_all`, no Alembic
- MySQL production validation

## Recommended Next Product Slices

1. Form 2307 workflow
   - Track `missing`, `requested`, `received`, `attached`
   - Add 2307 upload/file attachment
   - Show all `requires_2307=true` reconciliations

2. Reconciliation polish
   - Matched/reconciled list
   - Undo match
   - Manual match search
   - Better bank templates for BDO/BPI/Metrobank/UnionBank

3. PDF support
   - Add PDF-to-image dependency/path
   - Render first page or pages
   - OCR PDFs in background

4. Compliance exports
   - SLSP/SAWT export
   - 4-column journal export
   - BIR deadline flags

5. Client portal
   - Public upload links
   - Query/clarification flow
   - Mobile-first upload page

6. Billing/limits
   - Receipt limits per plan
   - Paymongo integration
   - Billing status/settings page

7. Deployment
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
