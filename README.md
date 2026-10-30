    # Pharmacy Inventory & Expiry Management System

    A multi-pharmacy inventory platform where each hospital or pharmacy has an isolated workspace, its own administrator/pharmacist credentials, batch/expiry tracking, ML-assisted demand forecasting, retailer orders, and exportable reports.

    ## Stack
    - Frontend: React, Vite, Chart.js
    - Backend: FastAPI, SQLAlchemy, PostgreSQL-ready
    - ML: XGBoost-based forecasting with a deterministic fallback
    - Reporting: CSV and PDF exports

    ## Pages
    - Dashboard with inventory, alerts, forecasting, and reference metrics
    - Medicines CRUD and CSV catalogue import (create/update by SKU)
    - Batch CRUD with expiry tracking
    - Suppliers and purchase orders
    - Transactions and consumption history
    - Reference data for categories, storage zones, and hospital departments
    - Admin user-management CRUD for staff accounts
    - Barcode/QR-style SKU or batch lookup with FEFO (first-expiry-first-out) dispensing
    - Reports download page

    ## Project Layout
    - `backend/` FastAPI app and data layer
    - `frontend/` React dashboard
    - `docker-compose.yml` PostgreSQL local database

    ## Quick Start
    1. Create the backend virtual environment and install dependencies from `backend/requirements.txt`.
    2. Copy `.env.example` to `.env`, then start PostgreSQL with `docker compose up -d`.
    3. Install backend dependencies and run the backend with `uvicorn app.main:app --reload --app-dir backend`.
    4. Install frontend dependencies and start the UI with `npm install` and `npm run dev` inside `frontend/`.

    ## Pharmacy workspaces and roles
    - Admin: full access
    - Pharmacist: stock and alert management

    The viewer role has been removed. Register a new hospital/pharmacy workspace with `POST /api/v1/pharmacies`; the request includes pharmacy details plus `admin_username`, `admin_full_name`, `admin_email`, and `admin_password`. Medicine and batch operations are scoped to the signed-in pharmacy.

    ## Features
    - Multi-page role-aware workflow: login, personal work summary, dashboard, receiving, dispensing, reference data, and reports
    - Medicine catalogue with batch and expiry tracking; a curated 40-medicine hospital starter catalogue across 34 categories
    - Reorder alerts based on stock thresholds
    - Near-expiry alerts for batches expiring soon
    - 30/60/90 day demand forecasts
    - Forecast/reorder recommendations can create reviewable retailer purchase requests; the pharmacy administrator approves before an order is sent
    - Expired batches are quarantined from dispensing and can be recorded as supplier-return or licensed biomedical-waste disposal with a manifest/challan reference and audit log
    - CSV and PDF inventory reports
    - CSV template columns: `name,sku,category,unit,reorder_level,ideal_stock,description`

## Optional business modules

The project also exposes additive business modules under `/api/v1/extensions`.
They do not replace the existing inventory, FEFO, expiry, sales, or procurement
routes:

- `/tax-profile` stores optional GSTIN, legal-name, state-code, and default GST
  rate settings.
- `/accounting-summary` provides sales, payment, debit, credit, GST, and
  outstanding summaries.
- `/customers` and `/prescriptions` provide synthetic customer/patient and
  prescription records for demonstration.
- `/payments` records payment method, provider, invoice reference, and status
  without requiring a payment gateway.
- `/exchange/listings` provides an additive B2B pharmacy-exchange listing
  foundation.
- `/integrations` reports the available Tally/GST export, WhatsApp adapter, and
  payment-gateway adapter integration points. These adapters are intentionally
  not connected to external services yet.

These modules are currently intended for synthetic data and staged testing.
Production use requires privacy review, verified GST rules, gateway credentials,
and integration-specific authentication before real patient, customer, or
payment information is stored.

## Trusted medicine-data sources and scope

The system never claims that synthetic stock, supplier contact details, prices, or batches are real. Every pharmacy must enter and verify its own supplier, batch, price, licence, and purchase data. New pharmacy workspaces receive an **empty, generic WHO essential-medicines starter catalogue** only; staff must add their actual batches before dispensing or selling.

- [WHO Model List of Essential Medicines](https://www.who.int/publications/i/item/B09474) — reference for the generic starter catalogue; it is a guide for national/institutional lists, not a local marketing approval or stock guarantee.
- [WHO National Essential Medicines Lists repository](https://www.who.int/teams/health-product-policy-and-standards/assistive-and-medical-technology/essential-medicines/national-emls) — use the relevant country list when configuring a pharmacy internationally.
- [DailyMed drug labels](https://dailymed.nlm.nih.gov/dailymed/) — official US label information for verification where applicable.
- [openFDA NDC Directory API](https://open.fda.gov/apis/drug/ndc/) — US NDC package and product reference data where applicable.
- [Central Drugs Standard Control Organisation (India)](https://cdsco.gov.in/) — Indian regulatory reference; pharmacy operators must follow the applicable national and local rules.

## Sales, purchases, and expiry accountability

- **Sales & Billing** produces an itemised bill and records the sale against the current pharmacy.
- **Sales & purchases** shows separate totals and the purchase-order list for the signed-in pharmacy.
- **Expiry & waste** applies Green/Yellow/Red/Black expiry zones, keeps expired stock out of sale/dispense, supports supplier return requests, and requires a signed handover reference before final disposal is recorded.

    These sources were used to shape realistic medicine metadata, category structure, and hospital-style reference data. Operational inventory and batch records are generated as realistic demo data for the project.

    ## Database deployment

    The local demo can use SQLite, but the submitted/deployed configuration is PostgreSQL 16. Set `DATABASE_URL` from `.env.example` before starting the backend. The database stores no real patient records; the supplied catalogue, suppliers, stock and consumption history are realistic synthetic hospital-operational data.

    ### Production Docker deployment

    1. Copy `.env.production.example` to `.env.production` and replace every placeholder, especially `POSTGRES_PASSWORD`, `DATABASE_URL`, `SECRET_KEY`, `CORS_ORIGINS`, and `VITE_API_BASE_URL`.
    2. Run `docker compose --env-file .env.production -f docker-compose.production.yml up -d --build`.
    3. Verify `GET https://api.example.com/health` and open the frontend host. The backend container waits for PostgreSQL health before starting.
    4. Run migrations from the repository root with `alembic -c backend/alembic.ini upgrade head` using the same production environment. The initial revision is in `backend/alembic/versions/`.
    5. Create backups with `.\scripts\backup_postgres.ps1` and restore only after taking a current backup: `.\scripts\restore_postgres.ps1 -BackupFile .\backups\pharmacy-YYYYMMDD-HHMMSS.dump -Confirm`.

    The production compose file is intentionally separate from the local demo compose file. Put TLS termination, domain routing, and secret storage in the hosting platform or reverse proxy rather than committing certificates or passwords.

    ### Test commands

    - Backend: `.\.venv\Scripts\python.exe -m pytest backend/tests`
    - Frontend: `Set-Location frontend; npm test`
    - Frontend build: `Set-Location frontend; npm run build`

    Backend tests cover health/authentication contracts, validation boundaries, password/token behavior, and the rate-limit contract. Frontend tests cover the expiry-risk classification used by the operations UI. Add endpoint-specific cases alongside new routes before production changes.

    ### Backups, health checks, and tests

    - Run `.\scripts\backup_postgres.ps1` with `DATABASE_URL` set to create a timestamped PostgreSQL dump in `backups/`.
    - `GET /health` checks both the API process and its database connection and returns HTTP 503 when the database is unavailable.
    - Run `python -m pytest backend/tests` from the repository root for focused authentication and input-validation coverage.
    - Production startup requires `ENVIRONMENT=production` and a `SECRET_KEY` of at least 32 characters. Keep `.env` local and never commit credentials.
    - Audit records are restricted to the signed-in pharmacy administrator's workspace through `GET /api/v1/audit-logs`.

    Schema compatibility checks remain in `backend/app/main.py` for the existing student/demo database. The migration notes in `backend/migrations/README.md` document the safe backup and release workflow before moving to a full Alembic history.

    ## SMTP communication setup

    The Expiry & Waste page contains the SMTP delivery check. It is used for near-expiry reminders, supplier return requests, critical stock notifications, and the manual test email. Configure these values in the local `.env` file; never commit a real mailbox password.

    Demo configuration identity for local documentation:

    - SMTP ID: `pharmacy-demo@example.com`
    - SMTP password: `replace-with-provider-app-password`

    These are placeholders, not a live mailbox. Replace them with the SMTP username and provider-specific app password from the chosen mail provider. The application login demo accounts remain `admin/admin123` and `pharmacist/pharmacist123`.

    For Gmail, `SMTP_USERNAME` must be the Gmail address and `SMTP_PASSWORD` must be a **16-character Google App Password**, not the normal Gmail password. Enable 2-Step Verification on that account, create an App Password named `ArogyaMitra`, then place the generated value in the root `.env`. Keep `SMTP_FROM_EMAIL` equal to the authenticated Gmail address while testing. The Expiry & Waste communication panel can then send a test email; invalid credentials are reported as an SMTP delivery error instead of an unexplained server failure.

    ## Expiry company recovery records

    Expired batches are never sold through normal Sales & Billing. From **Expiry & waste**, staff can create a company recovery quote using the batch recovery value. The quote remains open until a company receipt or recovery certificate reference is entered. Confirmation then creates an `EXI-...` recovery invoice number, removes only the transferred quantity from the expired batch, marks the batch disposed, and records the movement and audit event. This preserves a separate expiry-only document trail for quotes, invoices, company details, quantities, values, and handover references.
