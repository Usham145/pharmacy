from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    full_name: str
    email: str | None = None
    role: str
    pharmacy_id: int | None = None


class PharmacyCreate(BaseModel):
    name: str = Field(min_length=2, max_length=128)
    hospital_name: str | None = Field(default=None, max_length=128)
    licence_number: str | None = Field(default=None, max_length=64)
    address: str | None = Field(default=None, max_length=500)
    country: str | None = Field(default=None, max_length=64)


class PharmacyRead(PharmacyCreate):
    model_config = ConfigDict(from_attributes=True)
    id: int


class PharmacyRegistration(PharmacyCreate):
    admin_username: str = Field(min_length=3, max_length=64)
    admin_full_name: str = Field(min_length=2, max_length=128)
    admin_email: str | None = Field(default=None, max_length=128)
    admin_password: str = Field(min_length=8)


class UserCreate(BaseModel):
    username: str = Field(min_length=3, max_length=64)
    full_name: str = Field(min_length=2, max_length=128)
    email: str | None = Field(default=None, max_length=128)
    role: str = Field(pattern="^(admin|pharmacist)$")
    password: str = Field(min_length=8)
    pharmacy_id: int | None = None


class UserUpdate(BaseModel):
    full_name: str | None = Field(default=None, min_length=2, max_length=128)
    email: str | None = Field(default=None, max_length=128)
    role: str | None = Field(default=None, pattern="^(admin|pharmacist)$")
    password: str | None = Field(default=None, min_length=8)


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=256)


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
    waste_vendor: bool = False
    waste_license_number: str | None = None


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


class FinancialSummary(BaseModel):
    sales_total: float
    sales_count: int
    purchases_total: float
    purchase_count: int


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
    created_at: datetime


class MedicineCreate(BaseModel):
    name: str = Field(min_length=2, max_length=128)
    sku: str = Field(min_length=2, max_length=64)
    category: str = Field(min_length=2, max_length=64)
    unit: str = Field(min_length=1, max_length=16)
    reorder_level: int = Field(default=25, ge=0, le=1_000_000)
    ideal_stock: int = Field(default=100, ge=0, le=1_000_000)
    active: bool = True
    description: str | None = None


class MedicineUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=128)
    sku: str | None = Field(default=None, min_length=2, max_length=64)
    category: str | None = Field(default=None, min_length=2, max_length=64)
    unit: str | None = Field(default=None, min_length=1, max_length=16)
    reorder_level: int | None = Field(default=None, ge=0, le=1_000_000)
    ideal_stock: int | None = Field(default=None, ge=0, le=1_000_000)
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
    recovery_unit_price: float = 0
    received_on: date
    expiry_date: date
    location: str
    medicine_name: str | None = None
    disposal_status: str = "active"
    disposal_method: str | None = None
    disposal_reference: str | None = None
    disposed_on: date | None = None
    created_at: datetime


class ActivityRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    action_time: datetime
    action: str
    entity_name: str
    entity_id: int
    description: str


class BatchCreate(BaseModel):
    medicine_id: int
    batch_number: str = Field(min_length=1, max_length=64)
    supplier: str = Field(min_length=2, max_length=128)
    quantity: int = Field(ge=0, le=1_000_000)
    unit_price: float = Field(default=50.0, ge=0)
    recovery_unit_price: float = Field(default=0.0, ge=0)
    received_on: date
    expiry_date: date
    location: str = Field(default="Main Store", min_length=1, max_length=64)

    @model_validator(mode="after")
    def expiry_follows_receipt(self):
        if self.expiry_date <= self.received_on:
            raise ValueError("expiry_date must be after received_on")
        return self


class BatchUpdate(BaseModel):
    medicine_id: int | None = None
    batch_number: str | None = Field(default=None, min_length=1, max_length=64)
    supplier: str | None = Field(default=None, min_length=2, max_length=128)
    quantity: int | None = Field(default=None, ge=0, le=1_000_000)
    unit_price: float | None = Field(default=None, ge=0)
    recovery_unit_price: float | None = Field(default=None, ge=0)
    received_on: date | None = None
    expiry_date: date | None = None
    location: str | None = None

    @model_validator(mode="after")
    def valid_dates_when_both_present(self):
        if self.received_on is not None and self.expiry_date is not None and self.expiry_date <= self.received_on:
            raise ValueError("expiry_date must be after received_on")
        return self


class EquipmentCreate(BaseModel):
    name: str = Field(min_length=2, max_length=128)
    asset_number: str = Field(min_length=1, max_length=64)
    equipment_type: str = Field(min_length=2, max_length=64)
    waste_category: str = Field(min_length=2, max_length=64)
    quantity: int = Field(ge=0, le=1_000_000)
    unit: str = Field(default="piece", min_length=1, max_length=16)
    expiry_date: date | None = None
    condition: str = Field(default="usable", min_length=2, max_length=32)
    location: str = Field(default="Main Store", min_length=1, max_length=64)


class EquipmentRead(EquipmentCreate):
    model_config = ConfigDict(from_attributes=True)
    id: int
    waste_status: str


class EquipmentUpdate(BaseModel):
    name: str | None = None
    equipment_type: str | None = None
    waste_category: str | None = None
    quantity: int | None = None
    unit: str | None = None
    expiry_date: date | None = None
    condition: str | None = None
    location: str | None = None
    waste_status: str | None = None


class WastePickupCreate(BaseModel):
    vendor_name: str = Field(min_length=2, max_length=128)
    vendor_contact: str = Field(min_length=2, max_length=128)
    scheduled_date: date
    waste_category: str = Field(min_length=2, max_length=64)
    item_summary: str = Field(min_length=2, max_length=500)
    notes: str | None = None


class WastePickupRead(WastePickupCreate):
    model_config = ConfigDict(from_attributes=True)
    id: int
    pickup_number: str
    status: str
    manifest_number: str | None = None
    certificate_reference: str | None = None


class WastePickupUpdate(BaseModel):
    status: str | None = None
    manifest_number: str | None = None
    certificate_reference: str | None = None
    notes: str | None = None


class DisposalRequest(BaseModel):
    method: str = Field(min_length=2, max_length=64)
    pickup_contact: str = Field(min_length=2, max_length=128)
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
    handover_reference: str = Field(min_length=2, max_length=64)
    note: str | None = None


class SMTPStatus(BaseModel):
    configured: bool
    host: str
    port: int
    use_tls: bool
    username_configured: bool
    from_email: str


class SMTPTestRequest(BaseModel):
    recipient: str | None = None
    subject: str | None = None
    body: str | None = None


class DispenseRequest(BaseModel):
    lookup: str = Field(min_length=1, max_length=128)
    quantity: int = Field(gt=0, le=1_000_000)
    department: str = Field(min_length=2, max_length=64)
    note: str | None = None


class SaleCreate(BaseModel):
    lookup: str = Field(min_length=1, max_length=128)
    quantity: int = Field(gt=0, le=1_000_000)
    buyer_name: str = Field(min_length=2, max_length=128)
    buyer_phone: str | None = Field(default=None, max_length=24)


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
