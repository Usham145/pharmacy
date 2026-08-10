from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    full_name: Mapped[str] = mapped_column(String(128), nullable=False)
    email: Mapped[str | None] = mapped_column(String(128), nullable=True)
    role: Mapped[str] = mapped_column(String(32), nullable=False)
    password: Mapped[str] = mapped_column(String(128), nullable=False)
    pharmacy_id: Mapped[int | None] = mapped_column(ForeignKey("pharmacies.id"), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)


class MedicineCategory(Base):
    __tablename__ = "medicine_categories"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)


class Supplier(Base):
    __tablename__ = "suppliers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    company_name: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    contact_person: Mapped[str] = mapped_column(String(128), nullable=False)
    phone: Mapped[str] = mapped_column(String(24), nullable=False)
    email: Mapped[str] = mapped_column(String(128), nullable=False)
    gst_number: Mapped[str] = mapped_column(String(32), nullable=False)
    address: Mapped[str] = mapped_column(Text, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class HospitalDepartment(Base):
    __tablename__ = "hospital_departments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    floor: Mapped[str] = mapped_column(String(32), nullable=False)
    contact_extension: Mapped[str] = mapped_column(String(16), nullable=False)


class StorageLocation(Base):
    __tablename__ = "storage_locations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    code: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    temperature_zone: Mapped[str] = mapped_column(String(32), nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)


class PurchaseOrder(Base):
    __tablename__ = "purchase_orders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    po_number: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    supplier_name: Mapped[str] = mapped_column(String(128), nullable=False)
    order_date: Mapped[date] = mapped_column(Date, nullable=False)
    total_amount: Mapped[float] = mapped_column(Float, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="Pending", nullable=False)


class ProcurementRequest(Base):
    __tablename__ = "procurement_requests"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    request_number: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    supplier_name: Mapped[str] = mapped_column(String(128), nullable=False)
    supplier_email: Mapped[str] = mapped_column(String(128), nullable=False)
    trigger_summary: Mapped[str] = mapped_column(Text, nullable=False)
    item_lines: Mapped[str] = mapped_column(Text, nullable=False)  # JSON snapshot for an auditable order
    estimated_total: Mapped[float] = mapped_column(Float, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="pending_review", nullable=False)
    admin_notified_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)


class Pharmacy(Base):
    """A tenant workspace owned by one hospital or independent pharmacy."""
    __tablename__ = "pharmacies"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    hospital_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    licence_number: Mapped[str | None] = mapped_column(String(64), nullable=True)
    address: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)


class ProcurementInvoice(Base):
    __tablename__ = "procurement_invoices"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    invoice_number: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    procurement_request_id: Mapped[int] = mapped_column(ForeignKey("procurement_requests.id"), unique=True, nullable=False)
    amount: Mapped[float] = mapped_column(Float, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="proforma", nullable=False)
    generated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)


class SaleInvoice(Base):
    __tablename__ = "sale_invoices"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    invoice_number: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    buyer_name: Mapped[str] = mapped_column(String(128), nullable=False)
    buyer_phone: Mapped[str | None] = mapped_column(String(24), nullable=True)
    medicine_name: Mapped[str] = mapped_column(String(128), nullable=False)
    sku: Mapped[str] = mapped_column(String(64), nullable=False)
    batch_number: Mapped[str] = mapped_column(String(64), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    unit_price: Mapped[float] = mapped_column(Float, nullable=False)
    total_amount: Mapped[float] = mapped_column(Float, nullable=False)
    sold_by: Mapped[str] = mapped_column(String(64), nullable=False)
    sold_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)


class InventoryTransaction(Base):
    __tablename__ = "inventory_transactions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    transaction_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    medicine_id: Mapped[int] = mapped_column(ForeignKey("medicines.id"), nullable=False, index=True)
    transaction_type: Mapped[str] = mapped_column(String(32), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    reference: Mapped[str] = mapped_column(String(64), nullable=False)
    department: Mapped[str | None] = mapped_column(String(64), nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)


class DepartmentInventory(Base):
    """Stock physically held by a department after pharmacy issue."""
    __tablename__ = "department_inventory"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    pharmacy_id: Mapped[int] = mapped_column(ForeignKey("pharmacies.id"), nullable=False, index=True)
    department: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    medicine_id: Mapped[int] = mapped_column(ForeignKey("medicines.id"), nullable=False, index=True)
    batch_number: Mapped[str] = mapped_column(String(64), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    action_time: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    actor_username: Mapped[str] = mapped_column(String(64), nullable=False)
    action: Mapped[str] = mapped_column(String(128), nullable=False)
    entity_name: Mapped[str] = mapped_column(String(64), nullable=False)
    entity_id: Mapped[int] = mapped_column(Integer, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)


class Medicine(Base):
    __tablename__ = "medicines"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(128), index=True, nullable=False)
    sku: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    category: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    unit: Mapped[str] = mapped_column(String(16), nullable=False)
    reorder_level: Mapped[int] = mapped_column(Integer, default=25, nullable=False)
    ideal_stock: Mapped[int] = mapped_column(Integer, default=100, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    pharmacy_id: Mapped[int | None] = mapped_column(ForeignKey("pharmacies.id"), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    batches: Mapped[list[BatchStock]] = relationship(back_populates="medicine", cascade="all, delete-orphan")
    consumption_records: Mapped[list[ConsumptionRecord]] = relationship(back_populates="medicine", cascade="all, delete-orphan")


class BatchStock(Base):
    __tablename__ = "batch_stocks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    medicine_id: Mapped[int] = mapped_column(ForeignKey("medicines.id"), nullable=False, index=True)
    batch_number: Mapped[str] = mapped_column(String(64), nullable=False)
    supplier: Mapped[str] = mapped_column(String(128), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    unit_price: Mapped[float] = mapped_column(Float, default=50.0, nullable=False)
    received_on: Mapped[date] = mapped_column(Date, nullable=False)
    expiry_date: Mapped[date] = mapped_column(Date, nullable=False)
    location: Mapped[str] = mapped_column(String(64), default="Main Store", nullable=False)
    disposal_status: Mapped[str] = mapped_column(String(32), default="active", nullable=False)
    disposal_method: Mapped[str | None] = mapped_column(String(64), nullable=True)
    disposal_reference: Mapped[str | None] = mapped_column(String(64), nullable=True)
    disposed_on: Mapped[date | None] = mapped_column(Date, nullable=True)

    medicine: Mapped[Medicine] = relationship(back_populates="batches")


class ConsumptionRecord(Base):
    __tablename__ = "consumption_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    medicine_id: Mapped[int] = mapped_column(ForeignKey("medicines.id"), nullable=False, index=True)
    consumed_on: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    ward: Mapped[str] = mapped_column(String(64), nullable=False)

    medicine: Mapped[Medicine] = relationship(back_populates="consumption_records")
