from __future__ import annotations

import csv
import io
import json
from datetime import date, datetime, timedelta
from typing import Any

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from fastapi.responses import Response
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from app.core.config import get_settings
from app.db.session import get_db
from app.models.entities import BatchStock, ConsumptionRecord, DepartmentInventory, Medicine, Pharmacy, User
from app.schemas import (
    CategoryRead,
    AlertRead,
    AuthMeResponse,
    BatchCreate,
    BatchRead,
    BatchUpdate,
    DepartmentRead,
    DashboardSummary,
    InventoryInsight,
    FinancialSummary,
    ForecastResponse,
    LoginRequest,
    LoginResponse,
    LocationRead,
    MedicineCreate,
    MedicineRead,
    MedicineUpdate,
    PurchaseOrderRead,
    ProcurementLine,
    ProcurementRequestRead,
    SupplierRead,
    TransactionRead,
    DepartmentInventoryRead,
    UserRead,
    UserCreate,
    UserUpdate,
    DispenseRequest,
    SaleCreate,
    SaleInvoiceRead,
    ImportResult,
    DisposalRequest,
    CollectionConfirmation,
    SMTPStatus,
    SMTPTestRequest,
    PharmacyCreate,
    PharmacyRead,
    PharmacyRegistration,
)
from app.services.auth import create_access_token, get_current_user, hash_password, require_roles, verify_password
from app.services.forecast import forecast_consumption
from app.services.email_notifications import send_procurement_email
from app.services.seed import add_who_starter_catalogue
from app.models.entities import AuditLog, HospitalDepartment, InventoryTransaction, MedicineCategory, ProcurementInvoice, ProcurementRequest, PurchaseOrder, SaleInvoice, StorageLocation, Supplier

settings = get_settings()
router = APIRouter()


def _tenant_medicines(db: Session, user: User):
    return db.query(Medicine).filter(Medicine.pharmacy_id == user.pharmacy_id)


@router.post("/pharmacies", response_model=PharmacyRead, status_code=status.HTTP_201_CREATED)
def create_pharmacy(payload: PharmacyRegistration, db: Session = Depends(get_db), current_user: User = Depends(require_roles("platform_admin"))) -> PharmacyRead:
    """Platform Admin creates a pharmacy workspace and appoints its first administrator."""
    if db.query(User).filter(User.username == payload.admin_username.strip()).first():
        raise HTTPException(status_code=400, detail="Use a unique username for the first pharmacy account")
    if db.query(Pharmacy).filter(Pharmacy.name == payload.name.strip()).first():
        raise HTTPException(status_code=400, detail="A pharmacy with this name already exists")
    pharmacy = Pharmacy(name=payload.name.strip(), hospital_name=payload.hospital_name, licence_number=payload.licence_number, address=payload.address, country=payload.country)
    db.add(pharmacy)
    db.flush()
    user = User(username=payload.admin_username.strip(), full_name=payload.admin_full_name.strip(), email=payload.admin_email, role="admin", password=hash_password(payload.admin_password), pharmacy_id=pharmacy.id)
    db.add(user)
    db.commit()
    add_who_starter_catalogue(db, pharmacy.id)
    db.refresh(user)
    return PharmacyRead.model_validate(pharmacy)


@router.get("/pharmacies", response_model=list[PharmacyRead])
def list_pharmacies(db: Session = Depends(get_db), current_user: User = Depends(require_roles("platform_admin"))) -> list[PharmacyRead]:
    return [PharmacyRead.model_validate(pharmacy) for pharmacy in db.query(Pharmacy).order_by(Pharmacy.name.asc()).all()]


@router.get("/pharmacies/me", response_model=PharmacyRead)
def my_pharmacy(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> PharmacyRead:
    pharmacy = db.query(Pharmacy).filter(Pharmacy.id == current_user.pharmacy_id).first()
    if not pharmacy:
        raise HTTPException(status_code=404, detail="Pharmacy workspace not found")
    return PharmacyRead.model_validate(pharmacy)


def _notify_critical_stock(*, db: Session, medicine: Medicine, previous_total: int, current_total: int) -> None:
    """Notify the named pharmacy contacts once when stock crosses into the critical range."""
    if previous_total <= 5 or current_total > 5:
        return
    account_recipients = [
        user.email for user in db.query(User).filter(User.pharmacy_id == medicine.pharmacy_id, User.role.in_(["admin", "pharmacist"])).all()
        if user.email
    ]
    recipients = {email for email in (*account_recipients, settings.admin_alert_email, settings.pharmacist_alert_email) if email}
    if not recipients:
        return
    subject = f"Critical stock alert: {medicine.name}"
    body = (
        f"{medicine.name} ({medicine.sku}) has reached critical stock.\n\n"
        f"Available quantity: {current_total} {medicine.unit}\n"
        "Alert threshold: 5 units or fewer\n\n"
        "Please review stock and arrange replenishment if required."
    )
    delivered = []
    for recipient in recipients:
        try:
            if send_procurement_email(recipient=recipient, subject=subject, body=body):
                delivered.append(recipient)
        except Exception:
            # A notification outage must never block dispensing or a sale.
            continue
    if delivered:
        db.add(AuditLog(actor_username="system", action="critical_stock_email_sent", entity_name="medicine", entity_id=medicine.id, description=f"Critical stock alert emailed to {', '.join(delivered)}"))
        db.commit()


@router.post("/auth/login", response_model=LoginResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)) -> LoginResponse:
    user = db.query(User).filter(User.username == payload.username).first()
    if not user or not verify_password(user.password, payload.password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    token = create_access_token(user.username, user.role)
    return LoginResponse(access_token=token, user=UserRead.model_validate(user))


@router.get("/auth/me", response_model=AuthMeResponse)
def me(current_user: User = Depends(get_current_user)) -> AuthMeResponse:
    return AuthMeResponse(user=UserRead.model_validate(current_user))


@router.get("/users", response_model=list[UserRead])
def list_users(db: Session = Depends(get_db), current_user: User = Depends(require_roles("admin"))) -> list[UserRead]:
    return [UserRead.model_validate(user) for user in db.query(User).filter(User.pharmacy_id == current_user.pharmacy_id).order_by(User.username.asc()).all()]


@router.post("/users", response_model=UserRead, status_code=status.HTTP_201_CREATED)
def create_user(payload: UserCreate, db: Session = Depends(get_db), current_user: User = Depends(require_roles("admin"))) -> UserRead:
    if payload.role not in {"admin", "pharmacist"}:
        raise HTTPException(status_code=400, detail="Role must be admin or pharmacist")
    if db.query(User).filter(User.username == payload.username).first():
        raise HTTPException(status_code=400, detail="Username already exists")
    user = User(username=payload.username.strip(), full_name=payload.full_name.strip(), email=payload.email, role=payload.role, password=hash_password(payload.password), pharmacy_id=current_user.pharmacy_id)
    db.add(user)
    db.commit()
    db.refresh(user)
    return UserRead.model_validate(user)


@router.put("/users/{user_id}", response_model=UserRead)
def update_user(user_id: int, payload: UserUpdate, db: Session = Depends(get_db), current_user: User = Depends(require_roles("admin"))) -> UserRead:
    user = db.query(User).filter(User.id == user_id, User.pharmacy_id == current_user.pharmacy_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    changes = payload.model_dump(exclude_unset=True)
    if "role" in changes and changes["role"] not in {"admin", "pharmacist"}:
        raise HTTPException(status_code=400, detail="Invalid role")
    if "password" in changes:
        changes["password"] = hash_password(changes["password"])
    for field, value in changes.items():
        setattr(user, field, value)
    db.commit()
    db.refresh(user)
    return UserRead.model_validate(user)


@router.delete("/users/{user_id}")
def delete_user(user_id: int, db: Session = Depends(get_db), current_user: User = Depends(require_roles("admin"))) -> dict[str, str]:
    user = db.query(User).filter(User.id == user_id, User.pharmacy_id == current_user.pharmacy_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if user.id == current_user.id:
        raise HTTPException(status_code=400, detail="You cannot delete your own account")
    db.delete(user)
    db.commit()
    return {"detail": "User deleted"}


@router.get("/dashboard/summary", response_model=DashboardSummary)
def dashboard_summary(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> DashboardSummary:
    medicines = _tenant_medicines(db, current_user).count()
    batches = db.query(BatchStock).join(Medicine).filter(Medicine.pharmacy_id == current_user.pharmacy_id).count()
    total_units = db.query(func.coalesce(func.sum(BatchStock.quantity), 0)).join(Medicine).filter(Medicine.pharmacy_id == current_user.pharmacy_id).scalar() or 0
    low_stock_items = 0
    near_expiry_batches = 0

    today = date.today()
    for medicine in _tenant_medicines(db, current_user).options(joinedload(Medicine.batches)).all():
        stock = sum(batch.quantity for batch in medicine.batches if batch.disposal_status == "active")
        # A reorder level is a planning target. A low-stock safety alert is only
        # raised when the medicine has five or fewer usable units remaining.
        if stock <= 5:
            low_stock_items += 1
        near_expiry_batches += sum(
            1 for batch in medicine.batches if batch.expiry_date <= today + timedelta(days=settings.near_expiry_days)
        )

    monthly_consumption = (
        db.query(func.coalesce(func.sum(ConsumptionRecord.quantity), 0))
        .filter(ConsumptionRecord.consumed_on >= today - timedelta(days=30))
        .scalar()
        or 0
    )
    forecast_signal = "Stable" if low_stock_items == 0 and near_expiry_batches < 5 else "Needs Attention"

    return DashboardSummary(
        medicines=medicines,
        batches=batches,
        total_units=total_units,
        low_stock_items=low_stock_items,
        near_expiry_batches=near_expiry_batches,
        monthly_consumption=monthly_consumption,
        forecast_signal=forecast_signal,
    )


@router.get("/dashboard/insights", response_model=InventoryInsight)
def dashboard_insights(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("admin", "pharmacist")),
) -> InventoryInsight:
    return InventoryInsight(
        total_medicines=_tenant_medicines(db, current_user).count(),
        total_batches=db.query(BatchStock).join(Medicine).filter(Medicine.pharmacy_id == current_user.pharmacy_id).count(),
        total_suppliers=db.query(Supplier).count(),
        total_transactions=db.query(InventoryTransaction).count(),
        total_purchase_orders=db.query(PurchaseOrder).count(),
        total_departments=db.query(HospitalDepartment).count(),
        total_locations=db.query(StorageLocation).count(),
    )


@router.get("/medicines", response_model=list[MedicineRead])
def list_medicines(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("admin", "pharmacist")),
) -> list[MedicineRead]:
    medicines = _tenant_medicines(db, current_user).order_by(Medicine.name.asc()).all()
    return [MedicineRead.model_validate(medicine) for medicine in medicines]


@router.get("/categories", response_model=list[CategoryRead])
def list_categories(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("admin", "pharmacist")),
) -> list[CategoryRead]:
    return [CategoryRead.model_validate(category) for category in db.query(MedicineCategory).order_by(MedicineCategory.name.asc()).all()]


@router.post("/medicines", response_model=MedicineRead, status_code=status.HTTP_201_CREATED)
def create_medicine(
    payload: MedicineCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("admin", "pharmacist")),
) -> MedicineRead:
    if _tenant_medicines(db, current_user).filter(Medicine.sku == payload.sku).first():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="SKU already exists")
    medicine = Medicine(**payload.model_dump(), pharmacy_id=current_user.pharmacy_id)
    db.add(medicine)
    db.commit()
    db.refresh(medicine)
    return MedicineRead.model_validate(medicine)


@router.put("/medicines/{medicine_id}", response_model=MedicineRead)
def update_medicine(
    medicine_id: int,
    payload: MedicineUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("admin", "pharmacist")),
) -> MedicineRead:
    medicine = _tenant_medicines(db, current_user).filter(Medicine.id == medicine_id).first()
    if not medicine:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Medicine not found")

    update_data = payload.model_dump(exclude_unset=True)
    if "sku" in update_data:
        duplicate = _tenant_medicines(db, current_user).filter(Medicine.sku == update_data["sku"], Medicine.id != medicine_id).first()
        if duplicate:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="SKU already exists")

    for field, value in update_data.items():
        setattr(medicine, field, value)
    db.commit()
    db.refresh(medicine)
    return MedicineRead.model_validate(medicine)


@router.delete("/medicines/{medicine_id}")
def delete_medicine(
    medicine_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("admin", "pharmacist")),
) -> dict[str, str]:
    medicine = _tenant_medicines(db, current_user).filter(Medicine.id == medicine_id).first()
    if not medicine:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Medicine not found")
    db.delete(medicine)
    db.commit()
    return {"detail": "Medicine deleted"}


@router.post("/imports/medicines", response_model=ImportResult)
async def import_medicines(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("admin", "pharmacist")),
) -> ImportResult:
    """Import a CSV with name, sku, category, unit, reorder_level, ideal_stock, description."""
    if not (file.filename or "").lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="Please upload a CSV file")
    try:
        rows = csv.DictReader((await file.read()).decode("utf-8-sig").splitlines())
    except UnicodeDecodeError as error:
        raise HTTPException(status_code=400, detail="CSV must be UTF-8 encoded") from error
    created = updated = skipped = 0
    errors: list[str] = []
    for line, row in enumerate(rows, start=2):
        sku = (row.get("sku") or "").strip()
        name = (row.get("name") or "").strip()
        if not sku or not name:
            skipped += 1
            errors.append(f"Line {line}: name and sku are required")
            continue
        try:
            values = {
                "name": name, "sku": sku, "category": (row.get("category") or "Uncategorized").strip(),
                "unit": (row.get("unit") or "unit").strip(),
                "reorder_level": int(row.get("reorder_level") or 25), "ideal_stock": int(row.get("ideal_stock") or 100),
                "description": (row.get("description") or "").strip() or None,
            }
            medicine = _tenant_medicines(db, current_user).filter(Medicine.sku == sku).first()
            if medicine:
                for field, value in values.items(): setattr(medicine, field, value)
                updated += 1
            else:
                db.add(Medicine(**values, pharmacy_id=current_user.pharmacy_id))
                created += 1
        except ValueError:
            skipped += 1
            errors.append(f"Line {line}: reorder_level and ideal_stock must be whole numbers")
    db.commit()
    return ImportResult(created=created, updated=updated, skipped=skipped, errors=errors[:20])


@router.get("/batches", response_model=list[BatchRead])
def list_batches(
    medicine_id: int | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("admin", "pharmacist")),
) -> list[BatchRead]:
    query = db.query(BatchStock, Medicine.name.label("medicine_name")).join(Medicine, BatchStock.medicine_id == Medicine.id).filter(Medicine.pharmacy_id == current_user.pharmacy_id)
    if medicine_id is not None:
        query = query.filter(BatchStock.medicine_id == medicine_id)
    rows = query.order_by(BatchStock.expiry_date.asc()).all()
    return [
        BatchRead(
            id=batch.id,
            medicine_id=batch.medicine_id,
            batch_number=batch.batch_number,
            supplier=batch.supplier,
            quantity=batch.quantity,
            unit_price=batch.unit_price,
            received_on=batch.received_on,
            expiry_date=batch.expiry_date,
            location=batch.location,
            medicine_name=medicine_name,
        )
        for batch, medicine_name in rows
    ]


@router.get("/suppliers", response_model=list[SupplierRead])
def list_suppliers(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("admin", "pharmacist")),
) -> list[SupplierRead]:
    return [SupplierRead.model_validate(supplier) for supplier in db.query(Supplier).order_by(Supplier.company_name.asc()).all()]


@router.get("/departments", response_model=list[DepartmentRead])
def list_departments(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("admin", "pharmacist")),
) -> list[DepartmentRead]:
    return [DepartmentRead.model_validate(department) for department in db.query(HospitalDepartment).order_by(HospitalDepartment.name.asc()).all()]


@router.get("/locations", response_model=list[LocationRead])
def list_locations(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("admin", "pharmacist")),
) -> list[LocationRead]:
    return [LocationRead.model_validate(location) for location in db.query(StorageLocation).order_by(StorageLocation.code.asc()).all()]


@router.get("/transactions", response_model=list[TransactionRead])
def list_transactions(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("admin", "pharmacist")),
) -> list[TransactionRead]:
    rows = (
        db.query(InventoryTransaction, Medicine.name.label("medicine_name"))
        .join(Medicine, InventoryTransaction.medicine_id == Medicine.id)
        .order_by(InventoryTransaction.transaction_date.desc(), InventoryTransaction.id.desc())
        .all()
    )
    return [
        TransactionRead(
            id=row.id,
            transaction_date=row.transaction_date,
            medicine_id=row.medicine_id,
            medicine_name=medicine_name,
            transaction_type=row.transaction_type,
            quantity=row.quantity,
            reference=row.reference,
            department=row.department,
            note=row.note,
        )
        for row, medicine_name in rows
    ]


@router.get("/department-inventory", response_model=list[DepartmentInventoryRead])
def list_department_inventory(db: Session = Depends(get_db), current_user: User = Depends(require_roles("admin", "pharmacist"))) -> list[DepartmentInventoryRead]:
    rows = db.query(DepartmentInventory, Medicine.name).join(Medicine, DepartmentInventory.medicine_id == Medicine.id).filter(DepartmentInventory.pharmacy_id == current_user.pharmacy_id, DepartmentInventory.quantity > 0).order_by(DepartmentInventory.department, Medicine.name).all()
    return [DepartmentInventoryRead(id=item.id, department=item.department, medicine_id=item.medicine_id, medicine_name=name, batch_number=item.batch_number, quantity=item.quantity, updated_at=item.updated_at) for item, name in rows]


@router.get("/purchase-orders", response_model=list[PurchaseOrderRead])
def list_purchase_orders(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("admin", "pharmacist")),
) -> list[PurchaseOrderRead]:
    return [PurchaseOrderRead.model_validate(order) for order in db.query(PurchaseOrder).filter(PurchaseOrder.pharmacy_id == current_user.pharmacy_id).order_by(PurchaseOrder.order_date.desc()).all()]


@router.get("/reports/financial-summary", response_model=FinancialSummary)
def financial_summary(db: Session = Depends(get_db), current_user: User = Depends(require_roles("admin", "pharmacist"))) -> FinancialSummary:
    return FinancialSummary(
        sales_total=db.query(func.coalesce(func.sum(SaleInvoice.total_amount), 0)).filter(SaleInvoice.pharmacy_id == current_user.pharmacy_id).scalar() or 0,
        sales_count=db.query(SaleInvoice).filter(SaleInvoice.pharmacy_id == current_user.pharmacy_id).count(),
        purchases_total=db.query(func.coalesce(func.sum(PurchaseOrder.total_amount), 0)).filter(PurchaseOrder.pharmacy_id == current_user.pharmacy_id).scalar() or 0,
        purchase_count=db.query(PurchaseOrder).filter(PurchaseOrder.pharmacy_id == current_user.pharmacy_id).count(),
    )


def _procurement_read(request: ProcurementRequest, invoice: ProcurementInvoice | None = None) -> ProcurementRequestRead:
    return ProcurementRequestRead(
        id=request.id,
        request_number=request.request_number,
        supplier_name=request.supplier_name,
        supplier_email=request.supplier_email,
        trigger_summary=request.trigger_summary,
        item_lines=[ProcurementLine(**line) for line in json.loads(request.item_lines)],
        estimated_total=request.estimated_total,
        status=request.status,
        admin_notified_at=request.admin_notified_at,
        sent_at=request.sent_at,
        invoice_number=invoice.invoice_number if invoice else None,
    )


@router.get("/procurement/requests", response_model=list[ProcurementRequestRead])
def list_procurement_requests(
    db: Session = Depends(get_db), current_user: User = Depends(require_roles("admin")),
) -> list[ProcurementRequestRead]:
    requests = db.query(ProcurementRequest).filter(ProcurementRequest.pharmacy_id == current_user.pharmacy_id).order_by(ProcurementRequest.created_at.desc()).all()
    invoices = {invoice.procurement_request_id: invoice for invoice in db.query(ProcurementInvoice).all()}
    return [_procurement_read(request, invoices.get(request.id)) for request in requests]


@router.post("/procurement/scan", response_model=list[ProcurementRequestRead])
def create_procurement_requests_from_alerts(
    db: Session = Depends(get_db), current_user: User = Depends(require_roles("admin")),
) -> list[ProcurementRequestRead]:
    """Create one reviewable supplier request per alerting medicine and notify the admin."""
    alerts = _build_alerts(db, current_user)
    active_supplier = db.query(Supplier).filter(Supplier.active.is_(True)).order_by(Supplier.id.asc()).first()
    if not active_supplier:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Add an active supplier before creating procurement requests")

    existing_medicine_ids = {
        line["medicine_id"]
        for request in db.query(ProcurementRequest).filter(ProcurementRequest.pharmacy_id == current_user.pharmacy_id, ProcurementRequest.status.in_(["pending_review", "sent"])).all()
        for line in json.loads(request.item_lines)
    }
    alerts_by_medicine: dict[int, list[AlertRead]] = {}
    for alert in alerts:
        alerts_by_medicine.setdefault(alert.medicine_id, []).append(alert)

    created: list[ProcurementRequest] = []
    for medicine_id, medicine_alerts in alerts_by_medicine.items():
        if medicine_id in existing_medicine_ids:
            continue
        medicine = db.query(Medicine).filter(Medicine.id == medicine_id).first()
        if not medicine:
            continue
        stock = sum(batch.quantity for batch in medicine.batches)
        quantity = max(medicine.ideal_stock - stock, medicine.reorder_level, 1)
        reasons = ", ".join(sorted({alert.alert_type.replace("_", " ") for alert in medicine_alerts}))
        unit_price = settings.procurement_unit_price
        line = {"medicine_id": medicine.id, "medicine_name": medicine.name, "sku": medicine.sku, "quantity": quantity, "unit_price": unit_price, "line_total": quantity * unit_price, "reason": reasons}
        request_number = f"PR-{date.today():%Y%m%d}-{medicine.id:03d}"
        request = ProcurementRequest(
            request_number=request_number,
            supplier_name=active_supplier.company_name,
            supplier_email=active_supplier.email,
            trigger_summary=f"Automatic safety trigger: {reasons} for {medicine.name}.",
            item_lines=json.dumps([line]),
            estimated_total=line["line_total"],
            pharmacy_id=current_user.pharmacy_id,
        )
        db.add(request)
        created.append(request)
    db.commit()

    for request in created:
        body = f"Procurement review required\n\n{request.trigger_summary}\nRequest: {request.request_number}\nEstimated total: INR {request.estimated_total:,.2f}\n\nReview and send it from the ArogyaMitra procurement workspace."
        if send_procurement_email(recipient=settings.admin_alert_email, subject=f"Action needed: {request.request_number}", body=body):
            request.admin_notified_at = datetime.utcnow()
    db.commit()
    return [_procurement_read(request) for request in created]


@router.post("/procurement/requests/{request_id}/send", response_model=ProcurementRequestRead)
def approve_and_send_procurement_request(
    request_id: int, db: Session = Depends(get_db), current_user: User = Depends(require_roles("admin")),
) -> ProcurementRequestRead:
    request = db.query(ProcurementRequest).filter(ProcurementRequest.id == request_id, ProcurementRequest.pharmacy_id == current_user.pharmacy_id).first()
    if not request:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Procurement request not found")
    if request.status == "sent":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="This supplier order has already been sent")
    lines = json.loads(request.item_lines)
    order_text = "\n".join(f"- {line['medicine_name']} ({line['sku']}): {line['quantity']} units | INR {line['line_total']:,.2f}" for line in lines)
    sent = send_procurement_email(
        recipient=request.supplier_email,
        subject=f"Hospital purchase order {request.request_number}",
        body=f"Dear supplier,\n\nPlease supply the following medicines to the hospital.\n\n{order_text}\n\nEstimated total: INR {request.estimated_total:,.2f}\n\nRegards,\nArogyaMitra Hospital Pharmacy",
    )
    if not sent:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="SMTP is not configured. The order has not been sent.")
    request.status = "sent"
    request.sent_at = datetime.utcnow()
    po = PurchaseOrder(po_number=request.request_number.replace("PR-", "PO-"), supplier_name=request.supplier_name, order_date=date.today(), total_amount=request.estimated_total, status="Sent", pharmacy_id=current_user.pharmacy_id)
    invoice = ProcurementInvoice(invoice_number=request.request_number.replace("PR-", "INV-"), procurement_request_id=request.id, amount=request.estimated_total)
    db.add_all([po, invoice, AuditLog(actor_username=current_user.username, action="supplier_order_sent", entity_name="procurement_request", entity_id=request.id, description=f"Sent {request.request_number} to {request.supplier_email} and generated {invoice.invoice_number}")])
    db.commit()
    return _procurement_read(request, invoice)


@router.get("/audit-logs")
def list_audit_logs(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("admin")),
) -> list[dict[str, Any]]:
    logs = db.query(AuditLog).order_by(AuditLog.action_time.desc()).all()
    return [
        {
            "id": log.id,
            "action_time": log.action_time.isoformat(),
            "actor_username": log.actor_username,
            "action": log.action,
            "entity_name": log.entity_name,
            "entity_id": log.entity_id,
            "description": log.description,
        }
        for log in logs
    ]


@router.post("/batches", response_model=BatchRead, status_code=status.HTTP_201_CREATED)
def create_batch(
    payload: BatchCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("admin", "pharmacist")),
) -> BatchRead:
    medicine = _tenant_medicines(db, current_user).filter(Medicine.id == payload.medicine_id).first()
    if not medicine:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Medicine not found")
    batch = BatchStock(**payload.model_dump())
    db.add(batch)
    db.commit()
    db.refresh(batch)
    return BatchRead(
        id=batch.id,
        medicine_id=batch.medicine_id,
        batch_number=batch.batch_number,
        supplier=batch.supplier,
        quantity=batch.quantity,
        unit_price=batch.unit_price,
        received_on=batch.received_on,
        expiry_date=batch.expiry_date,
        location=batch.location,
        medicine_name=medicine.name,
    )


@router.put("/batches/{batch_id}", response_model=BatchRead)
def update_batch(
    batch_id: int,
    payload: BatchUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("admin", "pharmacist")),
) -> BatchRead:
    batch = db.query(BatchStock).join(Medicine).filter(BatchStock.id == batch_id, Medicine.pharmacy_id == current_user.pharmacy_id).first()
    if not batch:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Batch not found")

    update_data = payload.model_dump(exclude_unset=True)
    if "medicine_id" in update_data:
        medicine = _tenant_medicines(db, current_user).filter(Medicine.id == update_data["medicine_id"]).first()
        if not medicine:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Medicine not found")

    for field, value in update_data.items():
        setattr(batch, field, value)
    db.commit()
    db.refresh(batch)
    medicine = _tenant_medicines(db, current_user).filter(Medicine.id == batch.medicine_id).first()
    return BatchRead(
        id=batch.id,
        medicine_id=batch.medicine_id,
        batch_number=batch.batch_number,
        supplier=batch.supplier,
        quantity=batch.quantity,
        unit_price=batch.unit_price,
        received_on=batch.received_on,
        expiry_date=batch.expiry_date,
        location=batch.location,
        medicine_name=medicine.name if medicine else None,
    )


@router.delete("/batches/{batch_id}")
def delete_batch(
    batch_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("admin", "pharmacist")),
) -> dict[str, str]:
    batch = db.query(BatchStock).join(Medicine).filter(BatchStock.id == batch_id, Medicine.pharmacy_id == current_user.pharmacy_id).first()
    if not batch:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Batch not found")
    db.delete(batch)
    db.commit()
    return {"detail": "Batch deleted"}


@router.post("/batches/{batch_id}/collection-request", response_model=BatchRead)
def request_expiry_collection(
    batch_id: int,
    payload: DisposalRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("admin", "pharmacist")),
) -> BatchRead:
    """Quarantine expired stock and request verified collection; it remains non-saleable until pickup."""
    batch = db.query(BatchStock).join(Medicine).filter(BatchStock.id == batch_id, Medicine.pharmacy_id == current_user.pharmacy_id).first()
    if not batch:
        raise HTTPException(status_code=404, detail="Batch not found")
    if batch.expiry_date > date.today():
        raise HTTPException(status_code=400, detail="Only expired batches can enter the disposal workflow")
    if batch.disposal_status in {"collection_requested", "disposed"}:
        raise HTTPException(status_code=409, detail="A collection workflow is already active for this batch")
    batch.disposal_status = "collection_requested"
    batch.disposal_method = payload.method
    batch.disposal_reference = None
    batch.disposed_on = None
    db.add(AuditLog(actor_username=current_user.username, action="expired_stock_collection_requested", entity_name="batch", entity_id=batch.id, description=f"{batch.batch_number}: {payload.method}; contact {payload.pickup_contact}; planned pickup {payload.pickup_date or 'not set'}; {payload.note or ''}"))
    db.commit()
    medicine = _tenant_medicines(db, current_user).filter(Medicine.id == batch.medicine_id).first()
    return BatchRead(id=batch.id, medicine_id=batch.medicine_id, batch_number=batch.batch_number, supplier=batch.supplier, quantity=batch.quantity, unit_price=batch.unit_price, received_on=batch.received_on, expiry_date=batch.expiry_date, location=batch.location, medicine_name=medicine.name if medicine else None, disposal_status=batch.disposal_status, disposal_method=batch.disposal_method, disposal_reference=batch.disposal_reference, disposed_on=batch.disposed_on)


@router.post("/batches/{batch_id}/confirm-collection", response_model=BatchRead)
def confirm_expiry_collection(
    batch_id: int,
    payload: CollectionConfirmation,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("admin", "pharmacist")),
) -> BatchRead:
    """Close the chain of custody only after the supplier or licensed waste partner signs the handover."""
    batch = db.query(BatchStock).join(Medicine).filter(BatchStock.id == batch_id, Medicine.pharmacy_id == current_user.pharmacy_id).first()
    if not batch:
        raise HTTPException(status_code=404, detail="Batch not found")
    if batch.disposal_status != "collection_requested":
        raise HTTPException(status_code=409, detail="Request collection before confirming handover")
    batch.disposal_status = "disposed"
    batch.disposal_reference = payload.handover_reference.strip()
    batch.disposed_on = date.today()
    db.add(InventoryTransaction(transaction_date=date.today(), medicine_id=batch.medicine_id, transaction_type="Expiry disposal", quantity=batch.quantity, reference=batch.disposal_reference, note=payload.note or f"Collected through {batch.disposal_method}"))
    db.add(AuditLog(actor_username=current_user.username, action="expired_stock_collected", entity_name="batch", entity_id=batch.id, description=f"{batch.batch_number}: collected through {batch.disposal_method}; manifest {batch.disposal_reference}"))
    db.commit()
    medicine = _tenant_medicines(db, current_user).filter(Medicine.id == batch.medicine_id).first()
    return BatchRead(id=batch.id, medicine_id=batch.medicine_id, batch_number=batch.batch_number, supplier=batch.supplier, quantity=batch.quantity, unit_price=batch.unit_price, received_on=batch.received_on, expiry_date=batch.expiry_date, location=batch.location, medicine_name=medicine.name if medicine else None, disposal_status=batch.disposal_status, disposal_method=batch.disposal_method, disposal_reference=batch.disposal_reference, disposed_on=batch.disposed_on)


@router.post("/batches/{batch_id}/email-supplier-return")
def email_supplier_return(batch_id: int, db: Session = Depends(get_db), current_user: User = Depends(require_roles("admin", "pharmacist"))) -> dict[str, str]:
    batch = db.query(BatchStock).join(Medicine).filter(BatchStock.id == batch_id, Medicine.pharmacy_id == current_user.pharmacy_id).first()
    if not batch or batch.expiry_date > date.today():
        raise HTTPException(status_code=400, detail="An expired batch in this pharmacy is required")
    supplier = db.query(Supplier).filter(Supplier.company_name == batch.supplier).first()
    if not supplier or not supplier.email:
        raise HTTPException(status_code=400, detail="Original supplier email is not available")
    pharmacy = db.query(Pharmacy).filter(Pharmacy.id == current_user.pharmacy_id).first()
    body = f"Dear {supplier.contact_person},\n\nPlease arrange collection/return authorization for expired stock purchased from your organisation.\n\nPharmacy: {pharmacy.name if pharmacy else ''}\nMedicine batch: {batch.batch_number}\nQuantity: {batch.quantity}\nExpiry: {batch.expiry_date}\n\nPlease reply with collection date and return challan instructions.\n"
    if not send_procurement_email(recipient=supplier.email, subject=f"Expired-stock return request: {batch.batch_number}", body=body):
        raise HTTPException(status_code=503, detail="SMTP is not configured; add SMTP settings before sending email")
    db.add(AuditLog(actor_username=current_user.username, action="supplier_return_email_sent", entity_name="batch", entity_id=batch.id, description=f"Return request sent to {supplier.email}")); db.commit()
    return {"detail": f"Return request emailed to {supplier.email}"}


@router.get("/communications/smtp-status", response_model=SMTPStatus)
def get_smtp_status(db: Session = Depends(get_db), current_user: User = Depends(require_roles("admin", "pharmacist"))) -> SMTPStatus:
    return SMTPStatus.model_validate(smtp_configuration_status())


@router.post("/communications/test-email")
def send_test_email(
    payload: SMTPTestRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("admin", "pharmacist")),
) -> dict[str, str]:
    recipient = (payload.recipient or current_user.email or settings.admin_alert_email or settings.smtp_from_email).strip()
    if not recipient:
        raise HTTPException(status_code=400, detail="Add a recipient email or set SMTP_FROM_EMAIL before testing SMTP")
    pharmacy = db.query(Pharmacy).filter(Pharmacy.id == current_user.pharmacy_id).first()
    subject = (payload.subject or f"{settings.app_name} SMTP test").strip()
    body = (
        payload.body.strip()
        if payload.body and payload.body.strip()
        else (
            f"SMTP test message from {settings.app_name}\n\n"
            f"Pharmacy: {pharmacy.name if pharmacy else 'Unknown'}\n"
            f"User: {current_user.full_name} ({current_user.username})\n"
            f"Recipient: {recipient}\n\n"
            "If you received this message, the communication channel is working."
        )
    )
    if not send_procurement_email(recipient=recipient, subject=subject, body=body):
        raise HTTPException(status_code=503, detail="SMTP is not configured. Add SMTP_HOST and SMTP_FROM_EMAIL before sending mail.")
    db.add(AuditLog(actor_username=current_user.username, action="smtp_test_email_sent", entity_name="communication", entity_id=current_user.id, description=f"SMTP test email sent to {recipient}"))
    db.commit()
    return {"detail": f"Test email sent to {recipient}"}


@router.post("/batches/{batch_id}/email-expiry-reminder")
def email_expiry_reminder(batch_id: int, db: Session = Depends(get_db), current_user: User = Depends(require_roles("admin", "pharmacist"))) -> dict[str, str]:
    batch = db.query(BatchStock).join(Medicine).filter(BatchStock.id == batch_id, Medicine.pharmacy_id == current_user.pharmacy_id).first()
    if not batch:
        raise HTTPException(status_code=404, detail="Batch not found")
    days_left = (batch.expiry_date - date.today()).days
    if batch.expiry_date > date.today() + timedelta(days=settings.near_expiry_days):
        raise HTTPException(status_code=400, detail="Only near-expiry or expired batches can use the reminder workflow")
    supplier = db.query(Supplier).filter(Supplier.company_name == batch.supplier).first()
    if not supplier or not supplier.email:
        raise HTTPException(status_code=400, detail="Original supplier email is not available")
    pharmacy = db.query(Pharmacy).filter(Pharmacy.id == current_user.pharmacy_id).first()
    expiry_state = "expired" if batch.expiry_date < date.today() else f"{days_left} days from expiry"
    body = (
        f"Dear {supplier.contact_person},\n\n"
        f"Please review the medicine batch below for reverse logistics, replacement, or return credit.\n\n"
        f"Pharmacy: {pharmacy.name if pharmacy else ''}\n"
        f"Medicine batch: {batch.batch_number}\n"
        f"Medicine: {batch.medicine.name}\n"
        f"Quantity: {batch.quantity}\n"
        f"Expiry date: {batch.expiry_date} ({expiry_state})\n\n"
        "If a return or collection is possible, please confirm the pickup instructions and any authorization reference required.\n"
    )
    subject = f"Expiry reminder: {batch.batch_number}"
    if not send_procurement_email(recipient=supplier.email, subject=subject, body=body):
        raise HTTPException(status_code=503, detail="SMTP is not configured; add SMTP settings before sending email")
    db.add(AuditLog(actor_username=current_user.username, action="expiry_reminder_email_sent", entity_name="batch", entity_id=batch.id, description=f"Expiry reminder sent to {supplier.email}"))
    db.commit()
    return {"detail": f"Expiry reminder emailed to {supplier.email}"}


@router.post("/dispense", response_model=BatchRead)
def dispense_fefo(
    payload: DispenseRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("admin", "pharmacist")),
) -> BatchRead:
    """Accept a SKU or barcode/batch number, then dispense from the earliest-expiring valid batch (FEFO)."""
    lookup = payload.lookup.strip()
    if payload.quantity <= 0:
        raise HTTPException(status_code=400, detail="Quantity must be greater than zero")
    medicine = _tenant_medicines(db, current_user).filter(Medicine.sku == lookup).first()
    query = db.query(BatchStock).join(Medicine).filter(Medicine.pharmacy_id == current_user.pharmacy_id, BatchStock.quantity > 0, BatchStock.expiry_date >= date.today(), BatchStock.disposal_status == "active")
    if medicine:
        query = query.filter(BatchStock.medicine_id == medicine.id)
    else:
        query = query.filter(BatchStock.batch_number == lookup)
    batch = query.order_by(BatchStock.expiry_date.asc()).first()
    if not batch:
        raise HTTPException(status_code=404, detail="No usable batch found for this barcode, SKU, or batch number")
    if batch.quantity < payload.quantity:
        raise HTTPException(status_code=400, detail=f"Only {batch.quantity} units are available in FEFO batch {batch.batch_number}")
    medicine = _tenant_medicines(db, current_user).filter(Medicine.id == batch.medicine_id).first()
    previous_total = sum(item.quantity for item in medicine.batches) if medicine else batch.quantity
    batch.quantity -= payload.quantity
    department_stock = db.query(DepartmentInventory).filter(DepartmentInventory.pharmacy_id == current_user.pharmacy_id, DepartmentInventory.department == payload.department, DepartmentInventory.medicine_id == batch.medicine_id, DepartmentInventory.batch_number == batch.batch_number).first()
    if department_stock:
        department_stock.quantity += payload.quantity
    else:
        db.add(DepartmentInventory(pharmacy_id=current_user.pharmacy_id, department=payload.department, medicine_id=batch.medicine_id, batch_number=batch.batch_number, quantity=payload.quantity))
    db.add(InventoryTransaction(
        transaction_date=date.today(), medicine_id=batch.medicine_id, transaction_type="Dispense",
        quantity=payload.quantity, reference=f"FEFO-{batch.batch_number}", department=payload.department,
        note=payload.note or f"Barcode/QR lookup: {lookup}",
    ))
    db.commit()
    # A dispensing event can be the moment a medicine crosses its reorder level.
    # Procurement automation is best-effort and must never block a clinical issue.
    try:
        create_procurement_requests_from_alerts(db=db, current_user=current_user)
    except Exception:
        db.rollback()
    if medicine:
        _notify_critical_stock(db=db, medicine=medicine, previous_total=previous_total, current_total=sum(item.quantity for item in medicine.batches))
    medicine_name = db.query(Medicine.name).filter(Medicine.id == batch.medicine_id).scalar()
    return BatchRead(id=batch.id, medicine_id=batch.medicine_id, batch_number=batch.batch_number, supplier=batch.supplier,
        quantity=batch.quantity, unit_price=batch.unit_price, received_on=batch.received_on, expiry_date=batch.expiry_date, location=batch.location, medicine_name=medicine_name)


@router.post("/sales", response_model=SaleInvoiceRead, status_code=status.HTTP_201_CREATED)
def sell_medicine(
    payload: SaleCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("admin", "pharmacist")),
) -> SaleInvoiceRead:
    """Sell FEFO stock and return an itemised pharmacy bill."""
    if payload.quantity <= 0:
        raise HTTPException(status_code=400, detail="Quantity must be positive")
    lookup = payload.lookup.strip()
    medicine = _tenant_medicines(db, current_user).filter(Medicine.sku == lookup).first()
    query = db.query(BatchStock).join(Medicine).filter(Medicine.pharmacy_id == current_user.pharmacy_id, BatchStock.quantity > 0, BatchStock.expiry_date >= date.today(), BatchStock.disposal_status == "active")
    if medicine:
        query = query.filter(BatchStock.medicine_id == medicine.id)
    else:
        query = query.filter(BatchStock.batch_number == lookup)
    batch = query.order_by(BatchStock.expiry_date.asc()).first()
    if not batch:
        raise HTTPException(status_code=404, detail="No saleable batch found for this SKU or batch number")
    medicine = _tenant_medicines(db, current_user).filter(Medicine.id == batch.medicine_id).first()
    if not medicine or batch.quantity < payload.quantity:
        raise HTTPException(status_code=400, detail=f"Only {batch.quantity} units are available in batch {batch.batch_number}")

    previous_total = sum(item.quantity for item in medicine.batches)
    batch.quantity -= payload.quantity
    total = round(payload.quantity * batch.unit_price, 2)
    invoice = SaleInvoice(
        invoice_number=f"SAL-{datetime.utcnow():%Y%m%d%H%M%S%f}",
        buyer_name=payload.buyer_name.strip(), buyer_phone=payload.buyer_phone.strip() if payload.buyer_phone else None,
        medicine_name=medicine.name, sku=medicine.sku, batch_number=batch.batch_number,
        quantity=payload.quantity, unit_price=batch.unit_price, total_amount=total, sold_by=current_user.full_name, pharmacy_id=current_user.pharmacy_id,
    )
    db.add_all([invoice, InventoryTransaction(
        transaction_date=date.today(), medicine_id=medicine.id, transaction_type="Sale", quantity=payload.quantity,
        reference=invoice.invoice_number, department=None, note=f"Retail sale to {invoice.buyer_name}",
    )])
    db.commit()
    db.refresh(invoice)
    _notify_critical_stock(db=db, medicine=medicine, previous_total=previous_total, current_total=sum(item.quantity for item in medicine.batches))
    return SaleInvoiceRead.model_validate(invoice)


@router.get("/alerts", response_model=list[AlertRead])
def list_alerts(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("admin", "pharmacist")),
) -> list[AlertRead]:
    return _build_alerts(db, current_user)


@router.get("/forecasts/{medicine_id}", response_model=ForecastResponse)
def get_forecast(
    medicine_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("admin", "pharmacist")),
) -> ForecastResponse:
    medicine = _tenant_medicines(db, current_user).filter(Medicine.id == medicine_id).first()
    if not medicine:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Medicine not found")
    records = (
        db.query(ConsumptionRecord)
        .filter(ConsumptionRecord.medicine_id == medicine_id)
        .order_by(ConsumptionRecord.consumed_on.asc())
        .all()
    )
    forecast = forecast_consumption(records, settings.forecast_horizon_days)
    return ForecastResponse(
        medicine_id=medicine.id,
        medicine_name=medicine.name,
        recent_daily_avg=forecast["recent_daily_avg"],
        points=forecast["points"],
        recommendation=forecast["recommendation"],
    )


@router.get("/reports/inventory.csv")
def export_inventory_csv(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("admin", "pharmacist")),
) -> Response:
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["Medicine", "SKU", "Category", "Batch", "Quantity", "Expiry Date", "Reorder Level"])
    for medicine in _tenant_medicines(db, current_user).options(joinedload(Medicine.batches)).all():
        for batch in medicine.batches:
            writer.writerow(
                [medicine.name, medicine.sku, medicine.category, batch.batch_number, batch.quantity, batch.expiry_date.isoformat(), medicine.reorder_level]
            )
    headers = {"Content-Disposition": 'attachment; filename="inventory-report.csv"'}
    return Response(buffer.getvalue(), media_type="text/csv", headers=headers)


@router.get("/reports/alerts.csv")
def export_alerts_csv(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("admin", "pharmacist")),
) -> Response:
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["Alert Type", "Severity", "Medicine", "Batch", "Message", "Due On", "Quantity"])
    for alert in _build_alerts(db, current_user):
        writer.writerow(
            [alert.alert_type, alert.severity, alert.medicine_name, alert.batch_number or "", alert.message, alert.due_on.isoformat() if alert.due_on else "", alert.quantity]
        )
    headers = {"Content-Disposition": 'attachment; filename="alerts-report.csv"'}
    return Response(buffer.getvalue(), media_type="text/csv", headers=headers)


@router.get("/reports/alerts.pdf")
def export_alerts_pdf(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("admin", "pharmacist")),
) -> Response:
    alerts = _build_alerts(db, current_user)
    buffer = io.BytesIO()
    document = SimpleDocTemplate(buffer, pagesize=A4)
    styles = getSampleStyleSheet()
    elements: list[Any] = [Paragraph("Pharmacy Alerts Report", styles["Title"]), Spacer(1, 12)]

    rows = [["Type", "Severity", "Medicine", "Batch", "Due On", "Qty"]]
    for alert in alerts:
        rows.append(
            [
                alert.alert_type,
                alert.severity,
                alert.medicine_name,
                alert.batch_number or "-",
                alert.due_on.isoformat() if alert.due_on else "-",
                str(alert.quantity),
            ]
        )

    table = Table(rows, repeatRows=1)
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#183153")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cfd8e3")),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.whitesmoke, colors.HexColor("#eef3f8")]),
            ]
        )
    )
    elements.append(table)
    document.build(elements)
    headers = {"Content-Disposition": 'attachment; filename="alerts-report.pdf"'}
    return Response(buffer.getvalue(), media_type="application/pdf", headers=headers)


@router.get("/dashboard/forecast-trend")
def forecast_trend(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("admin", "pharmacist")),
    medicine_id: int | None = Query(default=None),
) -> dict[str, Any]:
    medicines = _tenant_medicines(db, current_user).order_by(Medicine.name.asc()).all()
    target = medicines[0] if medicine_id is None and medicines else None
    if medicine_id is not None:
        target = _tenant_medicines(db, current_user).filter(Medicine.id == medicine_id).first()
    if not target:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Medicine not found")
    records = (
        db.query(ConsumptionRecord)
        .filter(ConsumptionRecord.medicine_id == target.id)
        .order_by(ConsumptionRecord.consumed_on.asc())
        .all()
    )
    forecast = forecast_consumption(records, settings.forecast_horizon_days)
    return {
        "medicine": {"id": target.id, "name": target.name},
        "forecast": forecast,
    }


def _build_alerts(db: Session, current_user: User) -> list[AlertRead]:
    alerts: list[AlertRead] = []
    today = date.today()
    medicines = _tenant_medicines(db, current_user).options(joinedload(Medicine.batches)).order_by(Medicine.name.asc()).all()
    for medicine in medicines:
        stock_total = sum(batch.quantity for batch in medicine.batches if batch.disposal_status == "active" and batch.expiry_date >= today)
        # Safety policy: low-stock notifications start only when five or fewer
        # usable units remain, regardless of the planning reorder level.
        if stock_total <= 5:
            alerts.append(
                AlertRead(
                    id=len(alerts) + 1,
                    medicine_id=medicine.id,
                    medicine_name=medicine.name,
                    alert_type="low_stock",
                    severity="high",
                    message=f"{medicine.name} has critical stock: only {stock_total} {medicine.unit} remaining (alert threshold: 5).",
                    due_on=None,
                    quantity=stock_total,
                )
            )
        for batch in medicine.batches:
            if batch.disposal_status != "active":
                continue
            days_left = (batch.expiry_date - today).days
            if days_left <= settings.near_expiry_days:
                severity = "high" if days_left <= 30 else "medium"
                alerts.append(
                    AlertRead(
                        id=len(alerts) + 1,
                        medicine_id=medicine.id,
                        medicine_name=medicine.name,
                        batch_id=batch.id,
                        batch_number=batch.batch_number,
                        alert_type="near_expiry",
                        severity=severity,
                        message=f"Batch {batch.batch_number} expires in {days_left} days.",
                        due_on=batch.expiry_date,
                        quantity=batch.quantity,
                    )
                )
    return alerts
