from __future__ import annotations

import csv
import io
import json
from datetime import date, datetime, timedelta
from typing import Any

from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, UploadFile, status
from fastapi.responses import Response
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from sqlalchemy import func, or_
from sqlalchemy.orm import Session, joinedload

from app.core.config import get_settings
from app.db.session import get_db
from app.models.entities import BatchStock, ConsumptionRecord, Customer, DepartmentInventory, Medicine, Pharmacy, User, MedicalEquipment, WastePickup, WastePickupLink
from app.schemas import (
    CategoryRead,
    AlertRead,
    ActivityRead,
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
    DepartmentUsageRequest,
    UserRead,
    UserCreate,
    UserUpdate,
    PlatformUserUpdate,
    DispenseRequest,
    SaleCreate,
    SaleLineCreate,
    SaleInvoiceLineRead,
    SaleInvoiceRead,
    ImportResult,
    DisposalRequest,
    CollectionConfirmation,
    SMTPStatus,
    SMTPTestRequest,
    PharmacyCreate,
    PharmacyRead,
    PharmacyRegistration,
    EquipmentCreate,
    EquipmentRead,
    EquipmentUpdate,
    WastePickupCreate,
    WastePickupRead,
    WastePickupUpdate,
)
from app.services.auth import (
    check_login_rate_limit,
    clear_login_failures,
    create_access_token,
    get_current_user,
    hash_password,
    record_login_failure,
    require_roles,
    verify_password,
)
from app.services.forecast import forecast_consumption
from app.services.email_notifications import send_procurement_email
from app.services.seed import add_who_starter_catalogue
from app.models.entities import AccountingEntry, AuditLog, HospitalDepartment, InventoryTransaction, MedicineCategory, ProcurementInvoice, ProcurementRequest, PurchaseOrder, SaleInvoice, SaleInvoiceLine, StorageLocation, Supplier

settings = get_settings()
router = APIRouter()


def _tenant_medicines(db: Session, user: User):
    return db.query(Medicine).filter(Medicine.pharmacy_id == user.pharmacy_id)


def _available_units(
    medicine: Medicine,
    today: date | None = None,
    department_units_by_batch: dict[tuple[int, str], int] | None = None,
) -> int:
    as_of = today or date.today()
    if not medicine.active:
        return 0
    return sum(
        batch.quantity + (department_units_by_batch or {}).get((medicine.id, batch.batch_number), 0)
        for batch in medicine.batches
        if batch.disposal_status == "active" and batch.expiry_date >= as_of
    )


def _department_units_by_batch(db: Session, pharmacy_id: int) -> dict[tuple[int, str], int]:
    rows = (
        db.query(
            DepartmentInventory.medicine_id,
            DepartmentInventory.batch_number,
            func.sum(DepartmentInventory.quantity),
        )
        .join(Medicine, DepartmentInventory.medicine_id == Medicine.id)
        .filter(
            DepartmentInventory.pharmacy_id == pharmacy_id,
            Medicine.pharmacy_id == pharmacy_id,
            DepartmentInventory.quantity > 0,
        )
        .group_by(DepartmentInventory.medicine_id, DepartmentInventory.batch_number)
        .all()
    )
    return {(medicine_id, batch_number): int(quantity) for medicine_id, batch_number, quantity in rows}


def _record_activity(
    db: Session,
    user: User,
    action: str,
    entity_name: str,
    entity_id: int,
    description: str,
) -> None:
    db.add(
        AuditLog(
            actor_username=user.username,
            pharmacy_id=user.pharmacy_id,
            action=action,
            entity_name=entity_name,
            entity_id=entity_id,
            description=description,
        )
    )


def _refresh_equipment_waste_status(db: Session, pharmacy_id: int) -> None:
    today = date.today()
    changed = False
    for item in db.query(MedicalEquipment).filter(MedicalEquipment.pharmacy_id == pharmacy_id, MedicalEquipment.waste_status.in_(["active", "near_expiry", "expired"])).all():
        next_status = item.waste_status
        if item.condition in {"damaged", "contaminated"}:
            next_status = "quarantine"
        elif item.expiry_date and item.expiry_date <= today:
            next_status = "expired"
        elif item.expiry_date and item.expiry_date <= today + timedelta(days=settings.near_expiry_days):
            next_status = "near_expiry"
        else:
            next_status = "active"
        if item.waste_status != next_status:
            item.waste_status = next_status
            changed = True
    if changed:
        db.commit()


def _waste_pickup_read(db: Session, pickup: WastePickup) -> WastePickupRead:
    response = WastePickupRead.model_validate(pickup)
    links = db.query(WastePickupLink).filter(WastePickupLink.pickup_id == pickup.id).all()
    return response.model_copy(update={
        "equipment_ids": [link.equipment_id for link in links if link.equipment_id is not None],
        "batch_ids": [link.batch_id for link in links if link.batch_id is not None],
    })


def _mark_batch_collected(
    db: Session,
    batch: BatchStock,
    pharmacy_id: int,
    username: str,
    manifest_number: str,
) -> None:
    department_stocks = (
        db.query(DepartmentInventory)
        .filter(
            DepartmentInventory.pharmacy_id == pharmacy_id,
            DepartmentInventory.medicine_id == batch.medicine_id,
            DepartmentInventory.batch_number == batch.batch_number,
            DepartmentInventory.quantity > 0,
        )
        .with_for_update()
        .all()
    )
    department_quantity = sum(item.quantity for item in department_stocks)
    for item in department_stocks:
        item.quantity = 0
    batch.disposal_status = "disposed"
    batch.disposal_reference = manifest_number
    batch.disposed_on = date.today()
    disposed_quantity = batch.quantity + department_quantity
    db.add(InventoryTransaction(
        transaction_date=date.today(),
        medicine_id=batch.medicine_id,
        transaction_type="Expiry disposal",
        quantity=disposed_quantity,
        reference=manifest_number,
        note=f"Collected through {batch.disposal_method}; {department_quantity} units were in department stock",
    ))
    db.add(AuditLog(
        actor_username=username,
        pharmacy_id=pharmacy_id,
        action="expired_stock_collected",
        entity_name="batch",
        entity_id=batch.id,
        description=f"{batch.batch_number}: collected {disposed_quantity} units through {batch.disposal_method}; manifest {manifest_number}",
    ))


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


@router.put("/pharmacies/{pharmacy_id}", response_model=PharmacyRead)
def update_pharmacy(
    pharmacy_id: int,
    payload: PharmacyCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("platform_admin")),
) -> PharmacyRead:
    pharmacy = db.query(Pharmacy).filter(Pharmacy.id == pharmacy_id).first()
    if not pharmacy:
        raise HTTPException(status_code=404, detail="Pharmacy workspace not found")
    duplicate = db.query(Pharmacy).filter(Pharmacy.name == payload.name.strip(), Pharmacy.id != pharmacy_id).first()
    if duplicate:
        raise HTTPException(status_code=400, detail="A pharmacy with this name already exists")
    for field, value in payload.model_dump().items():
        setattr(pharmacy, field, value.strip() if isinstance(value, str) else value)
    db.commit()
    db.refresh(pharmacy)
    return PharmacyRead.model_validate(pharmacy)


@router.get("/platform/users", response_model=list[UserRead])
def list_platform_users(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("platform_admin")),
) -> list[UserRead]:
    return [UserRead.model_validate(user) for user in db.query(User).filter(User.role != "platform_admin").order_by(User.pharmacy_id, User.username).all()]


@router.put("/platform/users/{user_id}", response_model=UserRead)
def update_platform_user(
    user_id: int,
    payload: PlatformUserUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("platform_admin")),
) -> UserRead:
    user = db.query(User).filter(User.id == user_id, User.role != "platform_admin").first()
    if not user:
        raise HTTPException(status_code=404, detail="Pharmacy user not found")
    changes = payload.model_dump(exclude_unset=True)
    if "password" in changes:
        changes["password"] = hash_password(changes["password"])
    for field, value in changes.items():
        setattr(user, field, value.strip() if isinstance(value, str) else value)
    db.commit()
    db.refresh(user)
    return UserRead.model_validate(user)


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
        db.add(AuditLog(actor_username="system", pharmacy_id=medicine.pharmacy_id, action="critical_stock_email_sent", entity_name="medicine", entity_id=medicine.id, description=f"Critical stock alert emailed to {', '.join(delivered)}"))
        db.commit()


@router.post("/auth/login", response_model=LoginResponse)
def login(request: Request, payload: LoginRequest, db: Session = Depends(get_db)) -> LoginResponse:
    client_key = request.client.host if request.client else "unknown"
    check_login_rate_limit(client_key)
    user = db.query(User).filter(User.username == payload.username).first()
    if not user or not verify_password(user.password, payload.password):
        record_login_failure(client_key)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    clear_login_failures(client_key)
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
    today = date.today()
    total_units = (
        db.query(func.coalesce(func.sum(BatchStock.quantity), 0))
        .join(Medicine)
        .filter(
            Medicine.pharmacy_id == current_user.pharmacy_id,
            Medicine.active.is_(True),
            BatchStock.disposal_status == "active",
            BatchStock.expiry_date >= today,
        )
        .scalar()
        or 0
    )
    department_units_by_batch = _department_units_by_batch(db, current_user.pharmacy_id)
    department_units = 0
    low_stock_items = 0
    near_expiry_batches = 0

    for medicine in _tenant_medicines(db, current_user).options(joinedload(Medicine.batches)).all():
        stock = _available_units(medicine, today, department_units_by_batch)
        # A reorder level is a planning target. A low-stock safety alert is only
        # raised when the medicine has five or fewer usable units remaining.
        if medicine.active and stock <= 5:
            low_stock_items += 1
        for batch in medicine.batches:
            department_quantity = department_units_by_batch.get((medicine.id, batch.batch_number), 0)
            if medicine.active and batch.disposal_status == "active" and batch.expiry_date >= today:
                department_units += department_quantity
            if (
                batch.disposal_status == "active"
                and medicine.active
                and batch.quantity + department_quantity > 0
                and today <= batch.expiry_date <= today + timedelta(days=settings.near_expiry_days)
            ):
                near_expiry_batches += 1
    total_units += department_units

    monthly_consumption = (
        db.query(func.coalesce(func.sum(ConsumptionRecord.quantity), 0))
        .join(Medicine, ConsumptionRecord.medicine_id == Medicine.id)
        .filter(Medicine.pharmacy_id == current_user.pharmacy_id)
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
        total_transactions=db.query(InventoryTransaction).join(Medicine).filter(Medicine.pharmacy_id == current_user.pharmacy_id).count(),
        total_purchase_orders=db.query(PurchaseOrder).filter(PurchaseOrder.pharmacy_id == current_user.pharmacy_id).count(),
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
    db.flush()
    _record_activity(db, current_user, "medicine_added", "medicine", medicine.id, f"Added medicine {medicine.name} ({medicine.sku})")
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
    _record_activity(db, current_user, "medicine_updated", "medicine", medicine.id, f"Updated medicine {medicine.name} ({medicine.sku})")
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
    has_batches = db.query(BatchStock.id).filter(BatchStock.medicine_id == medicine_id).first()
    has_transactions = db.query(InventoryTransaction.id).filter(InventoryTransaction.medicine_id == medicine_id).first()
    has_department_stock = db.query(DepartmentInventory.id).filter(
        DepartmentInventory.medicine_id == medicine_id,
        DepartmentInventory.quantity > 0,
    ).first()
    has_consumption = db.query(ConsumptionRecord.id).filter(ConsumptionRecord.medicine_id == medicine_id).first()
    has_sales = db.query(SaleInvoice.id).filter(SaleInvoice.sku == medicine.sku).first()
    has_sale_lines = db.query(SaleInvoiceLine.id).filter(SaleInvoiceLine.medicine_id == medicine_id).first()
    if any((has_batches, has_transactions, has_department_stock, has_consumption, has_sales, has_sale_lines)):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This medicine has stock or transaction history and cannot be deleted. Deactivate it instead.",
        )
    db.delete(medicine)
    _record_activity(db, current_user, "medicine_deleted", "medicine", medicine.id, f"Deleted medicine {medicine.name} ({medicine.sku})")
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
                _record_activity(db, current_user, "medicine_imported", "medicine", medicine.id, f"Updated medicine {medicine.name} ({medicine.sku}) from CSV")
            else:
                medicine = Medicine(**values, pharmacy_id=current_user.pharmacy_id)
                db.add(medicine)
                db.flush()
                created += 1
                _record_activity(db, current_user, "medicine_imported", "medicine", medicine.id, f"Added medicine {medicine.name} ({medicine.sku}) from CSV")
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
            recovery_unit_price=batch.recovery_unit_price,
            received_on=batch.received_on,
            expiry_date=batch.expiry_date,
            location=batch.location,
            medicine_name=medicine_name,
            disposal_status=batch.disposal_status,
            disposal_method=batch.disposal_method,
            disposal_reference=batch.disposal_reference,
            disposed_on=batch.disposed_on,
            created_at=datetime.combine(batch.received_on, datetime.min.time()),
        )
        for batch, medicine_name in rows
    ]


@router.get("/waste/equipment", response_model=list[EquipmentRead])
def list_equipment(db: Session = Depends(get_db), current_user: User = Depends(require_roles("admin", "pharmacist"))) -> list[EquipmentRead]:
    _refresh_equipment_waste_status(db, current_user.pharmacy_id)
    return [EquipmentRead.model_validate(item) for item in db.query(MedicalEquipment).filter(MedicalEquipment.pharmacy_id == current_user.pharmacy_id).order_by(MedicalEquipment.expiry_date.asc().nullslast()).all()]


@router.post("/waste/equipment", response_model=EquipmentRead, status_code=status.HTTP_201_CREATED)
def create_equipment(payload: EquipmentCreate, db: Session = Depends(get_db), current_user: User = Depends(require_roles("admin", "pharmacist"))) -> EquipmentRead:
    if payload.quantity <= 0:
        raise HTTPException(status_code=400, detail="Quantity must be greater than zero")
    item = MedicalEquipment(**payload.model_dump(), pharmacy_id=current_user.pharmacy_id)
    db.add(item)
    db.commit()
    db.refresh(item)
    return EquipmentRead.model_validate(item)


@router.put("/waste/equipment/{equipment_id}", response_model=EquipmentRead)
def update_equipment(equipment_id: int, payload: EquipmentUpdate, db: Session = Depends(get_db), current_user: User = Depends(require_roles("admin", "pharmacist"))) -> EquipmentRead:
    item = db.query(MedicalEquipment).filter(MedicalEquipment.id == equipment_id, MedicalEquipment.pharmacy_id == current_user.pharmacy_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Equipment item not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(item, field, value)
    db.commit()
    db.refresh(item)
    return EquipmentRead.model_validate(item)


@router.get("/waste/pickups", response_model=list[WastePickupRead])
def list_waste_pickups(db: Session = Depends(get_db), current_user: User = Depends(require_roles("admin", "pharmacist"))) -> list[WastePickupRead]:
    pickups = db.query(WastePickup).filter(WastePickup.pharmacy_id == current_user.pharmacy_id).order_by(WastePickup.scheduled_date.desc()).all()
    return [_waste_pickup_read(db, item) for item in pickups]


@router.post("/waste/pickups", response_model=WastePickupRead, status_code=status.HTTP_201_CREATED)
def create_waste_pickup(payload: WastePickupCreate, db: Session = Depends(get_db), current_user: User = Depends(require_roles("admin", "pharmacist"))) -> WastePickupRead:
    if len(set(payload.equipment_ids)) != len(payload.equipment_ids) or len(set(payload.batch_ids)) != len(payload.batch_ids):
        raise HTTPException(status_code=400, detail="A waste item can only be selected once")
    if not payload.item_summary and not payload.equipment_ids and not payload.batch_ids:
        raise HTTPException(status_code=400, detail="Select registered waste items or enter an item summary")

    equipment_items = (
        db.query(MedicalEquipment)
        .filter(
            MedicalEquipment.pharmacy_id == current_user.pharmacy_id,
            MedicalEquipment.id.in_(payload.equipment_ids),
        )
        .all()
        if payload.equipment_ids else []
    )
    if len(equipment_items) != len(payload.equipment_ids):
        raise HTTPException(status_code=400, detail="One or more selected equipment items do not belong to this pharmacy")
    if any(item.waste_status in {"collection_scheduled", "collected"} for item in equipment_items):
        raise HTTPException(status_code=409, detail="One or more equipment items are already in a collection workflow")

    batch_items = (
        db.query(BatchStock)
        .join(Medicine)
        .filter(
            Medicine.pharmacy_id == current_user.pharmacy_id,
            BatchStock.id.in_(payload.batch_ids),
        )
        .all()
        if payload.batch_ids else []
    )
    if len(batch_items) != len(payload.batch_ids):
        raise HTTPException(status_code=400, detail="One or more selected medicine batches do not belong to this pharmacy")
    if any(batch.expiry_date > date.today() or batch.disposal_status == "disposed" for batch in batch_items):
        raise HTTPException(status_code=400, detail="Only expired, undisposed medicine batches can be scheduled for collection")

    item_link_conditions = []
    if payload.equipment_ids:
        item_link_conditions.append(WastePickupLink.equipment_id.in_(payload.equipment_ids))
    if payload.batch_ids:
        item_link_conditions.append(WastePickupLink.batch_id.in_(payload.batch_ids))
    if item_link_conditions:
        conflicting_links = db.query(WastePickupLink).join(WastePickup).filter(
            WastePickup.pharmacy_id == current_user.pharmacy_id,
            WastePickup.status.in_(["scheduled", "collected"]),
            or_(*item_link_conditions),
        ).first()
        if conflicting_links:
            raise HTTPException(status_code=409, detail="One or more waste items are already linked to an active pickup")

    item_summary = (payload.item_summary or "").strip()
    if not item_summary:
        labels = [f"{item.name} ({item.asset_number}) x{item.quantity}" for item in equipment_items]
        labels.extend(f"{batch.batch_number} x{batch.quantity}" for batch in batch_items)
        item_summary = "; ".join(labels)
    pickup = WastePickup(
        pickup_number=f"WP-{datetime.utcnow():%Y%m%d%H%M%S%f}",
        **payload.model_dump(exclude={"equipment_ids", "batch_ids", "item_summary"}),
        item_summary=item_summary,
        pharmacy_id=current_user.pharmacy_id,
    )
    db.add(pickup)
    db.flush()
    for item in equipment_items:
        item.waste_status = "collection_scheduled"
        db.add(WastePickupLink(pickup_id=pickup.id, equipment_id=item.id))
    for batch in batch_items:
        batch.disposal_status = "collection_requested"
        batch.disposal_method = "Licensed biomedical-waste collector"
        batch.disposal_reference = None
        batch.disposed_on = None
        db.add(WastePickupLink(pickup_id=pickup.id, batch_id=batch.id))
    db.commit()
    db.refresh(pickup)
    return _waste_pickup_read(db, pickup)


@router.put("/waste/pickups/{pickup_id}", response_model=WastePickupRead)
def update_waste_pickup(pickup_id: int, payload: WastePickupUpdate, db: Session = Depends(get_db), current_user: User = Depends(require_roles("admin", "pharmacist"))) -> WastePickupRead:
    pickup = db.query(WastePickup).filter(WastePickup.id == pickup_id, WastePickup.pharmacy_id == current_user.pharmacy_id).first()
    if not pickup:
        raise HTTPException(status_code=404, detail="Waste pickup not found")
    changes = payload.model_dump(exclude_unset=True)
    next_status = changes.get("status")
    if next_status is not None:
        valid_transition = (
            pickup.status == "scheduled" and next_status == "collected"
        ) or (
            pickup.status == "collected" and next_status == "destroyed"
        )
        if not valid_transition:
            raise HTTPException(status_code=409, detail="Pickup status must progress from scheduled to collected to destroyed")
        if next_status == "collected" and not (changes.get("manifest_number") or "").strip():
            raise HTTPException(status_code=400, detail="A manifest / handover reference is required")
        if next_status == "destroyed" and not (changes.get("certificate_reference") or "").strip():
            raise HTTPException(status_code=400, detail="A destruction certificate reference is required")

        links = db.query(WastePickupLink).filter(WastePickupLink.pickup_id == pickup.id).all()
        if next_status == "collected":
            for link in links:
                if link.equipment_id is not None:
                    equipment_item = db.query(MedicalEquipment).filter(
                        MedicalEquipment.id == link.equipment_id,
                        MedicalEquipment.pharmacy_id == current_user.pharmacy_id,
                    ).first()
                    if equipment_item:
                        equipment_item.waste_status = "collected"
                elif link.batch_id is not None:
                    batch = (
                        db.query(BatchStock)
                        .join(Medicine)
                        .filter(
                            BatchStock.id == link.batch_id,
                            Medicine.pharmacy_id == current_user.pharmacy_id,
                        )
                        .first()
                    )
                    if not batch or batch.disposal_status != "collection_requested":
                        raise HTTPException(status_code=409, detail="A linked medicine batch is no longer awaiting collection")
                    _mark_batch_collected(
                        db,
                        batch,
                        current_user.pharmacy_id,
                        current_user.username,
                        changes["manifest_number"].strip(),
                    )
    for field, value in changes.items():
        setattr(pickup, field, value)
    db.commit()
    db.refresh(pickup)
    return _waste_pickup_read(db, pickup)


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
        .filter(Medicine.pharmacy_id == current_user.pharmacy_id)
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
    rows = db.query(DepartmentInventory, Medicine.name).join(Medicine, DepartmentInventory.medicine_id == Medicine.id).filter(
        DepartmentInventory.pharmacy_id == current_user.pharmacy_id,
        Medicine.pharmacy_id == current_user.pharmacy_id,
        DepartmentInventory.quantity > 0,
    ).order_by(DepartmentInventory.department, Medicine.name).all()
    return [DepartmentInventoryRead(id=item.id, department=item.department, medicine_id=item.medicine_id, medicine_name=name, batch_number=item.batch_number, quantity=item.quantity, updated_at=item.updated_at) for item, name in rows]


@router.post("/department-inventory/use", response_model=DepartmentInventoryRead)
def use_department_inventory(
    payload: DepartmentUsageRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("admin", "pharmacist")),
) -> DepartmentInventoryRead:
    medicine = _tenant_medicines(db, current_user).filter(Medicine.id == payload.medicine_id).first()
    if not medicine:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Medicine not found")
    batch = db.query(BatchStock).filter(
        BatchStock.medicine_id == medicine.id,
        BatchStock.batch_number == payload.batch_number,
    ).first()
    if not batch or batch.disposal_status != "active" or batch.expiry_date < date.today():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Expired or quarantined batch stock cannot be used")
    stock = (
        db.query(DepartmentInventory)
        .filter(
            DepartmentInventory.pharmacy_id == current_user.pharmacy_id,
            DepartmentInventory.department == payload.department,
            DepartmentInventory.medicine_id == payload.medicine_id,
            DepartmentInventory.batch_number == payload.batch_number,
        )
        .with_for_update()
        .first()
    )
    if not stock:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Department stock record not found")
    if stock.quantity < payload.quantity:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Only {stock.quantity} units are available in {payload.department}")

    stock.quantity -= payload.quantity
    db.add(InventoryTransaction(
        transaction_date=date.today(),
        medicine_id=payload.medicine_id,
        transaction_type="Department use",
        quantity=payload.quantity,
        reference=f"DEPT-{payload.department}-{payload.batch_number}",
        department=payload.department,
        note=payload.note or f"Used in {payload.department}",
    ))
    db.add(ConsumptionRecord(
        medicine_id=payload.medicine_id,
        consumed_on=date.today(),
        quantity=payload.quantity,
        ward=payload.department,
    ))
    _record_activity(
        db,
        current_user,
        "department_stock_used",
        "department_inventory",
        stock.id,
        f"Used {payload.quantity} units of {medicine.name} in {payload.department} from batch {payload.batch_number}",
    )
    db.commit()
    db.refresh(stock)
    return DepartmentInventoryRead(
        id=stock.id,
        department=stock.department,
        medicine_id=stock.medicine_id,
        medicine_name=medicine.name,
        batch_number=stock.batch_number,
        quantity=stock.quantity,
        updated_at=stock.updated_at,
    )


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
    active_suppliers = (
        db.query(Supplier)
        .filter(Supplier.active.is_(True), Supplier.waste_vendor.is_(False))
        .order_by(Supplier.id.asc())
        .all()
    )
    if not active_suppliers:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Add an active medicine supplier before creating procurement requests")

    existing_requests = db.query(ProcurementRequest).filter(
        ProcurementRequest.pharmacy_id == current_user.pharmacy_id,
        ProcurementRequest.status.in_(["pending_review", "sent"]),
    ).all()
    existing_medicine_ids = {
        line["medicine_id"]
        for request in existing_requests
        for line in json.loads(request.item_lines)
    }
    supplier_index = len(existing_medicine_ids)
    alerts_by_medicine: dict[int, list[AlertRead]] = {}
    for alert in alerts:
        alerts_by_medicine.setdefault(alert.medicine_id, []).append(alert)

    created: list[ProcurementRequest] = []
    for medicine_id in sorted(alerts_by_medicine):
        medicine_alerts = alerts_by_medicine[medicine_id]
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
        supplier = active_suppliers[supplier_index % len(active_suppliers)]
        request = ProcurementRequest(
            request_number=request_number,
            supplier_name=supplier.company_name,
            supplier_email=supplier.email,
            trigger_summary=f"Automatic safety trigger: {reasons} for {medicine.name}.",
            item_lines=json.dumps([line]),
            estimated_total=line["line_total"],
            pharmacy_id=current_user.pharmacy_id,
        )
        db.add(request)
        created.append(request)
        supplier_index += 1
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
        if not settings.smtp_host or not settings.smtp_from_email:
            detail = "SMTP is not configured. The order has not been sent."
        else:
            detail = "SMTP delivery failed. Verify the SMTP host, port, credentials, and TLS settings; the order has not been sent."
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=detail)
    request.status = "sent"
    request.sent_at = datetime.utcnow()
    po = PurchaseOrder(po_number=request.request_number.replace("PR-", "PO-"), supplier_name=request.supplier_name, order_date=date.today(), total_amount=request.estimated_total, status="Sent", pharmacy_id=current_user.pharmacy_id)
    invoice = ProcurementInvoice(invoice_number=request.request_number.replace("PR-", "INV-"), procurement_request_id=request.id, amount=request.estimated_total)
    db.add_all([po, invoice, AuditLog(actor_username=current_user.username, pharmacy_id=current_user.pharmacy_id, action="supplier_order_sent", entity_name="procurement_request", entity_id=request.id, description=f"Sent {request.request_number} to {request.supplier_email} and generated {invoice.invoice_number}")])
    db.commit()
    return _procurement_read(request, invoice)


@router.get("/audit-logs")
def list_audit_logs(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("admin")),
) -> list[dict[str, Any]]:
    logs = db.query(AuditLog).filter(AuditLog.pharmacy_id == current_user.pharmacy_id).order_by(AuditLog.action_time.desc()).all()
    return [
        {
            "id": log.id,
            "action_time": log.action_time.isoformat(),
            "actor_username": log.actor_username,
            "pharmacy_id": log.pharmacy_id,
            "action": log.action,
            "entity_name": log.entity_name,
            "entity_id": log.entity_id,
            "description": log.description,
        }
        for log in logs
    ]


@router.get("/activity", response_model=list[ActivityRead])
def list_activity(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("admin", "pharmacist")),
) -> list[ActivityRead]:
    logs = (
        db.query(AuditLog)
        .filter(AuditLog.pharmacy_id == current_user.pharmacy_id)
        .order_by(AuditLog.action_time.desc(), AuditLog.id.desc())
        .limit(20)
        .all()
    )
    return [ActivityRead.model_validate(log) for log in logs]


@router.post("/batches", response_model=BatchRead, status_code=status.HTTP_201_CREATED)
def create_batch(
    payload: BatchCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("admin", "pharmacist")),
) -> BatchRead:
    medicine = _tenant_medicines(db, current_user).filter(Medicine.id == payload.medicine_id).first()
    if not medicine:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Medicine not found")
    if not medicine.active:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Activate this medicine before receiving a batch")
    if payload.quantity <= 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="A received batch must contain at least one unit")
    if db.query(BatchStock.id).filter(
        BatchStock.medicine_id == payload.medicine_id,
        BatchStock.batch_number == payload.batch_number,
    ).first():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="This batch number already exists for the selected medicine")
    batch = BatchStock(**payload.model_dump())
    db.add(batch)
    db.flush()
    db.add(InventoryTransaction(
        transaction_date=batch.received_on,
        medicine_id=medicine.id,
        transaction_type="Receipt",
        quantity=batch.quantity,
        reference=batch.batch_number,
        note=f"Received batch {batch.batch_number} from {batch.supplier} into {batch.location}",
    ))
    _record_activity(db, current_user, "batch_added", "batch", batch.id, f"Added batch {batch.batch_number} for {medicine.name}")
    db.commit()
    db.refresh(batch)
    return BatchRead(
        id=batch.id,
        medicine_id=batch.medicine_id,
        batch_number=batch.batch_number,
        supplier=batch.supplier,
        quantity=batch.quantity,
        unit_price=batch.unit_price,
        recovery_unit_price=batch.recovery_unit_price,
        received_on=batch.received_on,
        expiry_date=batch.expiry_date,
        location=batch.location,
        medicine_name=medicine.name,
        disposal_status=batch.disposal_status,
        disposal_method=batch.disposal_method,
        disposal_reference=batch.disposal_reference,
        disposed_on=batch.disposed_on,
        created_at=datetime.combine(batch.received_on, datetime.min.time()),
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
        if update_data["medicine_id"] != batch.medicine_id:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="A batch cannot be reassigned to another medicine. Create a new batch for that medicine instead.",
            )
    if "batch_number" in update_data and update_data["batch_number"] != batch.batch_number:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A batch number is a traceability identifier and cannot be changed after receipt.",
        )

    received_on = update_data.get("received_on", batch.received_on)
    expiry_date = update_data.get("expiry_date", batch.expiry_date)
    if expiry_date <= received_on:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Expiry date must be after the received date")
    previous_quantity = batch.quantity
    for field, value in update_data.items():
        setattr(batch, field, value)
    if batch.quantity != previous_quantity:
        difference = batch.quantity - previous_quantity
        db.add(InventoryTransaction(
            transaction_date=date.today(),
            medicine_id=batch.medicine_id,
            transaction_type="Stock increase" if difference > 0 else "Stock decrease",
            quantity=abs(difference),
            reference=batch.batch_number,
            note=f"Batch quantity adjusted from {previous_quantity} to {batch.quantity}",
        ))
    _record_activity(db, current_user, "batch_updated", "batch", batch.id, f"Updated batch {batch.batch_number}")
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
        recovery_unit_price=batch.recovery_unit_price,
        medicine_name=medicine.name if medicine else None,
        disposal_status=batch.disposal_status,
        disposal_method=batch.disposal_method,
        disposal_reference=batch.disposal_reference,
        disposed_on=batch.disposed_on,
        created_at=datetime.combine(batch.received_on, datetime.min.time()),
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
    department_stock = db.query(DepartmentInventory).filter(
        DepartmentInventory.pharmacy_id == current_user.pharmacy_id,
        DepartmentInventory.medicine_id == batch.medicine_id,
        DepartmentInventory.batch_number == batch.batch_number,
        DepartmentInventory.quantity > 0,
    ).first()
    if department_stock:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This batch still has units in department stock. Reconcile those units before deleting it.",
        )
    if batch.disposal_status != "active":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A batch with a disposal or collection record cannot be deleted.",
        )
    if batch.quantity > 0:
        db.add(InventoryTransaction(
            transaction_date=date.today(),
            medicine_id=batch.medicine_id,
            transaction_type="Stock decrease",
            quantity=batch.quantity,
            reference=batch.batch_number,
            note=f"Removed remaining {batch.quantity} units when batch {batch.batch_number} was deleted",
        ))
    db.query(DepartmentInventory).filter(
        DepartmentInventory.pharmacy_id == current_user.pharmacy_id,
        DepartmentInventory.medicine_id == batch.medicine_id,
        DepartmentInventory.batch_number == batch.batch_number,
        DepartmentInventory.quantity <= 0,
    ).delete(synchronize_session=False)
    db.delete(batch)
    _record_activity(db, current_user, "batch_deleted", "batch", batch.id, f"Deleted batch {batch.batch_number}")
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
    db.add(AuditLog(actor_username=current_user.username, pharmacy_id=current_user.pharmacy_id, action="expired_stock_collection_requested", entity_name="batch", entity_id=batch.id, description=f"{batch.batch_number}: {payload.method}; contact {payload.pickup_contact}; planned pickup {payload.pickup_date or 'not set'}; {payload.note or ''}"))
    db.commit()
    medicine = _tenant_medicines(db, current_user).filter(Medicine.id == batch.medicine_id).first()
    return BatchRead(id=batch.id, medicine_id=batch.medicine_id, batch_number=batch.batch_number, supplier=batch.supplier, quantity=batch.quantity, unit_price=batch.unit_price, recovery_unit_price=batch.recovery_unit_price, received_on=batch.received_on, expiry_date=batch.expiry_date, location=batch.location, medicine_name=medicine.name if medicine else None, disposal_status=batch.disposal_status, disposal_method=batch.disposal_method, disposal_reference=batch.disposal_reference, disposed_on=batch.disposed_on, created_at=datetime.combine(batch.received_on, datetime.min.time()))


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
    department_stocks = (
        db.query(DepartmentInventory)
        .filter(
            DepartmentInventory.pharmacy_id == current_user.pharmacy_id,
            DepartmentInventory.medicine_id == batch.medicine_id,
            DepartmentInventory.batch_number == batch.batch_number,
            DepartmentInventory.quantity > 0,
        )
        .with_for_update()
        .all()
    )
    department_quantity = sum(item.quantity for item in department_stocks)
    for item in department_stocks:
        item.quantity = 0
    batch.disposal_status = "disposed"
    batch.disposal_reference = payload.handover_reference.strip()
    batch.disposed_on = date.today()
    disposed_quantity = batch.quantity + department_quantity
    db.add(InventoryTransaction(transaction_date=date.today(), medicine_id=batch.medicine_id, transaction_type="Expiry disposal", quantity=disposed_quantity, reference=batch.disposal_reference, note=payload.note or f"Collected through {batch.disposal_method}; {department_quantity} units were in department stock"))
    db.add(AuditLog(actor_username=current_user.username, pharmacy_id=current_user.pharmacy_id, action="expired_stock_collected", entity_name="batch", entity_id=batch.id, description=f"{batch.batch_number}: collected {disposed_quantity} units through {batch.disposal_method}; manifest {batch.disposal_reference}"))
    db.commit()
    medicine = _tenant_medicines(db, current_user).filter(Medicine.id == batch.medicine_id).first()
    return BatchRead(id=batch.id, medicine_id=batch.medicine_id, batch_number=batch.batch_number, supplier=batch.supplier, quantity=batch.quantity, unit_price=batch.unit_price, recovery_unit_price=batch.recovery_unit_price, received_on=batch.received_on, expiry_date=batch.expiry_date, location=batch.location, medicine_name=medicine.name if medicine else None, disposal_status=batch.disposal_status, disposal_method=batch.disposal_method, disposal_reference=batch.disposal_reference, disposed_on=batch.disposed_on, created_at=datetime.combine(batch.received_on, datetime.min.time()))


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
    db.add(AuditLog(actor_username=current_user.username, pharmacy_id=current_user.pharmacy_id, action="supplier_return_email_sent", entity_name="batch", entity_id=batch.id, description=f"Return request sent to {supplier.email}")); db.commit()
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
    db.add(AuditLog(actor_username=current_user.username, pharmacy_id=current_user.pharmacy_id, action="smtp_test_email_sent", entity_name="communication", entity_id=current_user.id, description=f"SMTP test email sent to {recipient}"))
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
    db.add(AuditLog(actor_username=current_user.username, pharmacy_id=current_user.pharmacy_id, action="expiry_reminder_email_sent", entity_name="batch", entity_id=batch.id, description=f"Expiry reminder sent to {supplier.email}"))
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
    medicine = _tenant_medicines(db, current_user).filter(
        (Medicine.sku == lookup) | (func.lower(Medicine.name) == lookup.lower())
    ).first()
    if medicine and not medicine.active:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="This medicine is inactive and cannot be dispensed")
    query = db.query(BatchStock).join(Medicine).filter(Medicine.pharmacy_id == current_user.pharmacy_id, Medicine.active.is_(True), BatchStock.quantity > 0, BatchStock.expiry_date >= date.today(), BatchStock.disposal_status == "active")
    if medicine:
        query = query.filter(BatchStock.medicine_id == medicine.id)
    else:
        query = query.filter(BatchStock.batch_number == lookup)
    batches = query.order_by(BatchStock.expiry_date.asc(), BatchStock.id.asc()).with_for_update().all()
    if not batches:
        raise HTTPException(status_code=404, detail="No usable batch found for this barcode, SKU, or batch number")
    available_quantity = sum(item.quantity for item in batches)
    if available_quantity < payload.quantity:
        raise HTTPException(status_code=400, detail=f"Only {available_quantity} units are available for this medicine")
    medicine = _tenant_medicines(db, current_user).filter(Medicine.id == batches[0].medicine_id).first()
    department_units_by_batch = _department_units_by_batch(db, current_user.pharmacy_id)
    previous_total = _available_units(medicine, department_units_by_batch=department_units_by_batch) if medicine else available_quantity
    remaining = payload.quantity
    consumed_batches: list[str] = []
    last_batch = batches[0]
    for batch in batches:
        if remaining <= 0:
            break
        issued = min(batch.quantity, remaining)
        batch.quantity -= issued
        remaining -= issued
        last_batch = batch
        consumed_batches.append(f"{batch.batch_number}:{issued}")
        department_stock = db.query(DepartmentInventory).filter(
            DepartmentInventory.pharmacy_id == current_user.pharmacy_id,
            DepartmentInventory.department == payload.department,
            DepartmentInventory.medicine_id == batch.medicine_id,
            DepartmentInventory.batch_number == batch.batch_number,
        ).first()
        if department_stock:
            department_stock.quantity += issued
        else:
            db.add(DepartmentInventory(
                pharmacy_id=current_user.pharmacy_id,
                department=payload.department,
                medicine_id=batch.medicine_id,
                batch_number=batch.batch_number,
                quantity=issued,
            ))
    db.add(InventoryTransaction(
        transaction_date=date.today(), medicine_id=last_batch.medicine_id, transaction_type="Dispense",
        quantity=payload.quantity, reference=f"FEFO-{','.join(consumed_batches)}", department=payload.department,
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
        department_units_by_batch = _department_units_by_batch(db, current_user.pharmacy_id)
        _notify_critical_stock(
            db=db,
            medicine=medicine,
            previous_total=previous_total,
            current_total=_available_units(medicine, department_units_by_batch=department_units_by_batch),
        )
    medicine_name = db.query(Medicine.name).filter(Medicine.id == last_batch.medicine_id).scalar()
    return BatchRead(id=last_batch.id, medicine_id=last_batch.medicine_id, batch_number=last_batch.batch_number, supplier=last_batch.supplier,
        quantity=last_batch.quantity, unit_price=last_batch.unit_price, recovery_unit_price=last_batch.recovery_unit_price, received_on=last_batch.received_on, expiry_date=last_batch.expiry_date, location=last_batch.location, medicine_name=medicine_name,
        disposal_status=last_batch.disposal_status, disposal_method=last_batch.disposal_method, disposal_reference=last_batch.disposal_reference, disposed_on=last_batch.disposed_on, created_at=datetime.combine(last_batch.received_on, datetime.min.time()), available_quantity=_available_units(medicine) if medicine else 0)


@router.post("/sales", response_model=SaleInvoiceRead, status_code=status.HTTP_201_CREATED)
def sell_medicine(
    payload: SaleCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("admin", "pharmacist")),
) -> SaleInvoiceRead:
    """Sell FEFO stock and return an itemised pharmacy bill."""
    customer = None
    if payload.customer_id is not None:
        customer = db.query(Customer).filter(
            Customer.id == payload.customer_id,
            Customer.pharmacy_id == current_user.pharmacy_id,
            Customer.active.is_(True),
        ).first()
        if not customer:
            raise HTTPException(status_code=404, detail="Customer not found in this pharmacy")
    if payload.items is not None:
        requested_items = payload.items
    elif payload.lookup is not None and payload.quantity is not None:
        requested_items = [SaleLineCreate(lookup=payload.lookup, quantity=payload.quantity)]
    else:
        raise HTTPException(status_code=422, detail="Provide at least one sale item")
    prepared_items: list[tuple[Medicine, list[BatchStock], int, int]] = []
    seen_medicine_ids: set[int] = set()
    department_units_by_batch = _department_units_by_batch(db, current_user.pharmacy_id)
    for requested in requested_items:
        lookup = requested.lookup.strip()
        medicine = _tenant_medicines(db, current_user).filter(
            (Medicine.sku == lookup) | (func.lower(Medicine.name) == lookup.lower())
        ).first()
        if medicine and not medicine.active:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="This medicine is inactive and cannot be sold")
        query = db.query(BatchStock).join(Medicine).filter(
            Medicine.pharmacy_id == current_user.pharmacy_id,
            Medicine.active.is_(True),
            BatchStock.quantity > 0,
            BatchStock.expiry_date >= date.today(),
            BatchStock.disposal_status == "active",
        )
        if medicine:
            query = query.filter(BatchStock.medicine_id == medicine.id)
        else:
            query = query.filter(BatchStock.batch_number == lookup)
        batches = query.order_by(BatchStock.expiry_date.asc(), BatchStock.id.asc()).with_for_update().all()
        if not batches:
            raise HTTPException(status_code=404, detail=f"No saleable batch found for {lookup}")
        medicine = _tenant_medicines(db, current_user).filter(Medicine.id == batches[0].medicine_id).first()
        total_available = sum(batch.quantity for batch in batches)
        if not medicine or total_available < requested.quantity:
            raise HTTPException(status_code=400, detail=f"Only {total_available} units are available for {lookup}")
        if medicine.id in seen_medicine_ids:
            raise HTTPException(status_code=400, detail="Add each medicine to the bill only once")
        seen_medicine_ids.add(medicine.id)
        previous_total = _available_units(medicine, department_units_by_batch=department_units_by_batch)
        prepared_items.append((medicine, batches, requested.quantity, previous_total))

    invoice_number = f"SAL-{datetime.utcnow():%Y%m%d%H%M%S%f}"
    buyer_name = customer.name if customer else payload.buyer_name.strip()
    buyer_phone = customer.phone if customer else payload.buyer_phone.strip() if payload.buyer_phone else None
    invoice_line_values: list[dict[str, Any]] = []
    transactions: list[InventoryTransaction] = []
    consumption_records: list[ConsumptionRecord] = []
    total = 0.0
    total_quantity = 0
    for medicine, batches, requested_quantity, _ in prepared_items:
        remaining = requested_quantity
        line_total = 0.0
        consumed_batches: list[str] = []
        for batch in batches:
            if remaining <= 0:
                break
            consumed = min(batch.quantity, remaining)
            batch.quantity -= consumed
            remaining -= consumed
            line_total += consumed * batch.unit_price
            consumed_batches.append(f"{batch.batch_number} ({consumed})")
        line_total = round(line_total, 2)
        unit_price = round(line_total / requested_quantity, 2)
        total += line_total
        total_quantity += requested_quantity
        invoice_line_values.append({
            "medicine_id": medicine.id,
            "medicine_name": medicine.name,
            "sku": medicine.sku,
            "batch_number": ", ".join(consumed_batches),
            "quantity": requested_quantity,
            "unit_price": unit_price,
            "total_amount": line_total,
        })
        transactions.append(InventoryTransaction(
            transaction_date=date.today(), medicine_id=medicine.id, transaction_type="Sale",
            quantity=requested_quantity, reference=invoice_number, department=None,
            note=f"Retail sale to {buyer_name}; FEFO batches: {', '.join(consumed_batches)}",
        ))
        consumption_records.append(ConsumptionRecord(
            medicine_id=medicine.id, consumed_on=date.today(), quantity=requested_quantity, ward="Retail",
        ))
    total = round(total, 2)
    first_line = invoice_line_values[0]
    invoice_count = len(invoice_line_values)
    invoice = SaleInvoice(
        invoice_number=invoice_number,
        buyer_name=buyer_name,
        buyer_phone=buyer_phone,
        medicine_name=first_line["medicine_name"] if invoice_count == 1 else "Multiple items",
        sku=first_line["sku"] if invoice_count == 1 else "MULTIPLE",
        batch_number=first_line["batch_number"] if invoice_count == 1 else "Multiple",
        quantity=total_quantity,
        unit_price=round(total / total_quantity, 2),
        total_amount=total, sold_by=current_user.full_name, pharmacy_id=current_user.pharmacy_id,
        customer_id=customer.id if customer else None,
    )
    db.add(invoice)
    db.flush()
    db.add_all([
        *[
            SaleInvoiceLine(sale_invoice_id=invoice.id, **line_values)
            for line_values in invoice_line_values
        ],
        *transactions,
        *consumption_records,
        AccountingEntry(
            pharmacy_id=current_user.pharmacy_id, entry_type="sale", reference=invoice.invoice_number,
            description=f"Sale of {total_quantity} units across {invoice_count} medicine(s) to {buyer_name}",
            debit=total, credit=total,
        ),
    ])
    db.commit()
    db.refresh(invoice)
    for medicine, _, _, previous_total in prepared_items:
        department_units_by_batch = _department_units_by_batch(db, current_user.pharmacy_id)
        _notify_critical_stock(
            db=db,
            medicine=medicine,
            previous_total=previous_total,
            current_total=_available_units(medicine, department_units_by_batch=department_units_by_batch),
        )
    return _sale_invoice_read(db, invoice)


def _sale_invoice_read(
    db: Session,
    invoice: SaleInvoice,
    lines: list[SaleInvoiceLine] | None = None,
) -> SaleInvoiceRead:
    invoice_lines = lines if lines is not None else db.query(SaleInvoiceLine).filter(
        SaleInvoiceLine.sale_invoice_id == invoice.id
    ).order_by(SaleInvoiceLine.id.asc()).all()
    if not invoice_lines:
        medicine_id = db.query(Medicine.id).filter(Medicine.sku == invoice.sku).scalar()
        items = [SaleInvoiceLineRead(
            medicine_id=medicine_id,
            medicine_name=invoice.medicine_name,
            sku=invoice.sku,
            batch_number=invoice.batch_number,
            quantity=invoice.quantity,
            unit_price=invoice.unit_price,
            total_amount=invoice.total_amount,
        )]
    else:
        items = [SaleInvoiceLineRead.model_validate(line) for line in invoice_lines]
    return SaleInvoiceRead.model_validate(invoice).model_copy(update={"items": items})


@router.get("/sales", response_model=list[SaleInvoiceRead])
def list_sales(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("admin", "pharmacist")),
) -> list[SaleInvoice]:
    invoices = db.query(SaleInvoice).filter(
        SaleInvoice.pharmacy_id == current_user.pharmacy_id
    ).order_by(SaleInvoice.sold_at.desc()).all()
    invoice_ids = [invoice.id for invoice in invoices]
    lines_by_invoice: dict[int, list[SaleInvoiceLine]] = {}
    if invoice_ids:
        for line in db.query(SaleInvoiceLine).filter(
            SaleInvoiceLine.sale_invoice_id.in_(invoice_ids)
        ).order_by(SaleInvoiceLine.id.asc()).all():
            lines_by_invoice.setdefault(line.sale_invoice_id, []).append(line)
    return [
        _sale_invoice_read(db, invoice, lines_by_invoice.get(invoice.id, []))
        for invoice in invoices
    ]


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
    writer.writerow(["Medicine", "SKU", "Category", "Batch", "Quantity", "Expiry Date", "Reorder Level", "Stock Location"])
    for medicine in _tenant_medicines(db, current_user).options(joinedload(Medicine.batches)).all():
        batches_by_number = {batch.batch_number: batch for batch in medicine.batches}
        for batch in medicine.batches:
            writer.writerow(
                [medicine.name, medicine.sku, medicine.category, batch.batch_number, batch.quantity, batch.expiry_date.isoformat(), medicine.reorder_level, batch.location]
            )
        department_rows = db.query(DepartmentInventory).filter(
            DepartmentInventory.pharmacy_id == current_user.pharmacy_id,
            DepartmentInventory.medicine_id == medicine.id,
            DepartmentInventory.quantity > 0,
        ).all()
        for stock in department_rows:
            batch = batches_by_number.get(stock.batch_number)
            if batch:
                writer.writerow([
                    medicine.name,
                    medicine.sku,
                    medicine.category,
                    stock.batch_number,
                    stock.quantity,
                    batch.expiry_date.isoformat(),
                    medicine.reorder_level,
                    f"Department: {stock.department}",
                ])
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
    department_units_by_batch = _department_units_by_batch(db, current_user.pharmacy_id)
    medicines = _tenant_medicines(db, current_user).options(joinedload(Medicine.batches)).order_by(Medicine.name.asc()).all()
    for medicine in medicines:
        stock_total = _available_units(medicine, today, department_units_by_batch)
        # Safety policy: low-stock notifications start only when five or fewer
        # usable units remain, regardless of the planning reorder level.
        if medicine.active and stock_total <= 5:
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
            batch_quantity = batch.quantity + department_units_by_batch.get((medicine.id, batch.batch_number), 0)
            if batch.disposal_status != "active" or batch_quantity <= 0:
                continue
            days_left = (batch.expiry_date - today).days
            if 0 <= days_left <= settings.near_expiry_days:
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
                        quantity=batch_quantity,
                    )
                )
    return alerts
