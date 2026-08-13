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

    The viewer role has been removed. Register a new hospital/pharmacy workspace with `POST /api/v1/pharmacies/register`; the request includes pharmacy details plus `admin_username`, `admin_full_name`, `admin_email`, and `admin_password`. Medicine and batch operations are scoped to the signed-in pharmacy.

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
