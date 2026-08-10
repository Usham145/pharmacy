from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    full_name: str
    email: str | None = None
    role: str
    pharmacy_id: int | None = None


class PharmacyCreate(BaseModel):
    name: str
    hospital_name: str | None = None
    licence_number: str | None = None
    address: str | None = None


class PharmacyRead(PharmacyCreate):
    model_config = ConfigDict(from_attributes=True)
    id: int


class PharmacyRegistration(PharmacyCreate):
    admin_username: str
    admin_full_name: str
    admin_email: str | None = None
    admin_password: str


class UserCreate(BaseModel):
    username: str
    full_name: str
    email: str | None = None
    role: str
    password: str
    pharmacy_id: int | None = None


class UserUpdate(BaseModel):
    full_name: str | None = None
    email: str | None = None
    role: str | None = None
    password: str | None = None


class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserRead


class AuthMeResponse(BaseModel):
    user: UserRead


class SupplierRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    company_name: str
    contact_person: str
    phone: str
    email: str
    gst_number: str
    address: str
    active: bool


class DepartmentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    floor: str
    contact_extension: str


class LocationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    code: str
    name: str
    temperature_zone: str
    notes: str | None = None


class PurchaseOrderRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    po_number: str
    supplier_name: str
    order_date: date
    total_amount: float
    status: str


class ProcurementLine(BaseModel):
    medicine_id: int
    medicine_name: str
    sku: str
    quantity: int
    unit_price: float
    line_total: float
    reason: str


class ProcurementRequestRead(BaseModel):
    id: int
    request_number: str
    supplier_name: str
    supplier_email: str
    trigger_summary: str
    item_lines: list[ProcurementLine]
    estimated_total: float
    status: str
    admin_notified_at: datetime | None = None
    sent_at: datetime | None = None
    invoice_number: str | None = None


class TransactionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    transaction_date: date
    medicine_id: int
    medicine_name: str | None = None
    transaction_type: str
    quantity: int
    reference: str
    department: str | None = None
    note: str | None = None


class CategoryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    description: str | None = None


class InventoryInsight(BaseModel):
    total_medicines: int
    total_batches: int
    total_suppliers: int
    total_transactions: int
    total_purchase_orders: int
    total_departments: int
    total_locations: int


class MedicineRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    sku: str
    category: str
    unit: str
    reorder_level: int
    ideal_stock: int
    active: bool
    description: str | None = None


class MedicineCreate(BaseModel):
    name: str
    sku: str
    category: str
    unit: str
    reorder_level: int = 25
    ideal_stock: int = 100
    active: bool = True
    description: str | None = None


class MedicineUpdate(BaseModel):
    name: str | None = None
    sku: str | None = None
    category: str | None = None
    unit: str | None = None
    reorder_level: int | None = None
    ideal_stock: int | None = None
    active: bool | None = None
    description: str | None = None


class BatchRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    medicine_id: int
    batch_number: str
    supplier: str
    quantity: int
    unit_price: float
    received_on: date
    expiry_date: date
    location: str
    medicine_name: str | None = None
    disposal_status: str = "active"
    disposal_method: str | None = None
    disposal_reference: str | None = None
    disposed_on: date | None = None


class BatchCreate(BaseModel):
    medicine_id: int
    batch_number: str
    supplier: str
    quantity: int
    unit_price: float = 50.0
    received_on: date
    expiry_date: date
    location: str = "Main Store"


class BatchUpdate(BaseModel):
    medicine_id: int | None = None
    batch_number: str | None = None
    supplier: str | None = None
    quantity: int | None = None
    unit_price: float | None = None
    received_on: date | None = None
    expiry_date: date | None = None
    location: str | None = None


class DisposalRequest(BaseModel):
    method: str
    pickup_contact: str
    pickup_date: date | None = None
    note: str | None = None


class DepartmentInventoryRead(BaseModel):
    id: int
    department: str
    medicine_id: int
    medicine_name: str
    batch_number: str
    quantity: int
    updated_at: datetime


class CollectionConfirmation(BaseModel):
    handover_reference: str
    note: str | None = None


class DispenseRequest(BaseModel):
    lookup: str
    quantity: int
    department: str
    note: str | None = None


class SaleCreate(BaseModel):
    lookup: str
    quantity: int
    buyer_name: str
    buyer_phone: str | None = None


class SaleInvoiceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    invoice_number: str
    buyer_name: str
    buyer_phone: str | None = None
    medicine_name: str
    sku: str
    batch_number: str
    quantity: int
    unit_price: float
    total_amount: float
    sold_by: str
    sold_at: datetime


class ImportResult(BaseModel):
    created: int
    updated: int
    skipped: int
    errors: list[str] = []


class AlertRead(BaseModel):
    id: int
    medicine_id: int
    medicine_name: str
    batch_id: int | None = None
    batch_number: str | None = None
    alert_type: str
    severity: str
    message: str
    due_on: date | None = None
    quantity: int


class ForecastPoint(BaseModel):
    horizon_days: int
    predicted_quantity: float


class ForecastResponse(BaseModel):
    medicine_id: int
    medicine_name: str
    recent_daily_avg: float
    points: list[ForecastPoint]
    recommendation: int


class DashboardSummary(BaseModel):
    medicines: int
    batches: int
    total_units: int
    low_stock_items: int
    near_expiry_batches: int
    monthly_consumption: int
    forecast_signal: str
