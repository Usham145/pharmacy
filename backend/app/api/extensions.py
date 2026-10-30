from __future__ import annotations

import json
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.entities import (
    AccountingEntry,
    Customer,
    ExchangeListing,
    IntegrationEvent,
    PaymentRecord,
    PharmacyTaxProfile,
    Prescription,
    SaleInvoice,
    User,
    Medicine,
)
from app.services.auth import get_current_user, require_roles

router = APIRouter(prefix="/extensions", tags=["optional business modules"])


class TaxProfilePayload(BaseModel):
    gstin: str | None = None
    legal_name: str | None = None
    default_gst_rate: float = Field(default=0, ge=0, le=100)
    state_code: str | None = None


class TaxProfileRead(TaxProfilePayload):
    model_config = ConfigDict(from_attributes=True)
    id: int
    pharmacy_id: int


class CustomerPayload(BaseModel):
    name: str
    phone: str | None = None
    email: str | None = None
    credit_limit: float = Field(default=0, ge=0)


class CustomerRead(CustomerPayload):
    model_config = ConfigDict(from_attributes=True)
    id: int
    pharmacy_id: int
    loyalty_points: int
    active: bool


class PrescriptionPayload(BaseModel):
    patient_name: str
    doctor_name: str | None = None
    prescription_number: str
    medicine_summary: str
    prescribed_on: date
    customer_id: int | None = None
    notes: str | None = None


class PrescriptionRead(PrescriptionPayload):
    model_config = ConfigDict(from_attributes=True)
    id: int
    pharmacy_id: int
    status: str


class PaymentPayload(BaseModel):
    amount: float = Field(gt=0)
    method: str = Field(min_length=2, max_length=32)
    invoice_number: str | None = None
    provider: str | None = None


class PaymentRead(PaymentPayload):
    model_config = ConfigDict(from_attributes=True)
    id: int
    pharmacy_id: int
    reference: str
    status: str


class ExchangePayload(BaseModel):
    medicine_id: int
    quantity: int = Field(gt=0)
    asking_price: float = Field(default=0, ge=0)
    listing_type: str = "offer"
    notes: str | None = None


class ExchangeRead(ExchangePayload):
    model_config = ConfigDict(from_attributes=True)
    id: int
    pharmacy_id: int
    status: str


@router.get("/tax-profile", response_model=TaxProfileRead | None)
def get_tax_profile(db: Session = Depends(get_db), current_user: User = Depends(require_roles("admin", "pharmacist"))):
    return db.query(PharmacyTaxProfile).filter(PharmacyTaxProfile.pharmacy_id == current_user.pharmacy_id).first()


@router.put("/tax-profile", response_model=TaxProfileRead)
def save_tax_profile(payload: TaxProfilePayload, db: Session = Depends(get_db), current_user: User = Depends(require_roles("admin"))):
    profile = db.query(PharmacyTaxProfile).filter(PharmacyTaxProfile.pharmacy_id == current_user.pharmacy_id).first()
    if not profile:
        profile = PharmacyTaxProfile(pharmacy_id=current_user.pharmacy_id)
        db.add(profile)
    for key, value in payload.model_dump().items():
        setattr(profile, key, value.strip() if isinstance(value, str) else value)
    db.commit()
    db.refresh(profile)
    return profile


@router.get("/accounting-summary")
def accounting_summary(db: Session = Depends(get_db), current_user: User = Depends(require_roles("admin", "pharmacist"))):
    pharmacy_id = current_user.pharmacy_id
    sales = db.query(func.coalesce(func.sum(SaleInvoice.total_amount), 0)).filter(SaleInvoice.pharmacy_id == pharmacy_id).scalar() or 0
    payments = db.query(func.coalesce(func.sum(PaymentRecord.amount), 0)).filter(PaymentRecord.pharmacy_id == pharmacy_id, PaymentRecord.status == "recorded").scalar() or 0
    debit = db.query(func.coalesce(func.sum(AccountingEntry.debit), 0)).filter(AccountingEntry.pharmacy_id == pharmacy_id).scalar() or 0
    credit = db.query(func.coalesce(func.sum(AccountingEntry.credit), 0)).filter(AccountingEntry.pharmacy_id == pharmacy_id).scalar() or 0
    gst = db.query(func.coalesce(func.sum(AccountingEntry.gst_amount), 0)).filter(AccountingEntry.pharmacy_id == pharmacy_id).scalar() or 0
    return {"sales_total": sales, "payments_received": payments, "debit_total": debit, "credit_total": credit, "gst_total": gst, "outstanding": round(max(sales - payments, 0), 2)}


@router.get("/customers", response_model=list[CustomerRead])
def list_customers(db: Session = Depends(get_db), current_user: User = Depends(require_roles("admin", "pharmacist"))):
    return db.query(Customer).filter(Customer.pharmacy_id == current_user.pharmacy_id, Customer.active.is_(True)).order_by(Customer.name).all()


@router.post("/customers", response_model=CustomerRead, status_code=status.HTTP_201_CREATED)
def create_customer(payload: CustomerPayload, db: Session = Depends(get_db), current_user: User = Depends(require_roles("admin", "pharmacist"))):
    customer = Customer(pharmacy_id=current_user.pharmacy_id, **payload.model_dump())
    db.add(customer)
    db.commit()
    db.refresh(customer)
    return customer


@router.get("/prescriptions", response_model=list[PrescriptionRead])
def list_prescriptions(db: Session = Depends(get_db), current_user: User = Depends(require_roles("admin", "pharmacist"))):
    return db.query(Prescription).filter(Prescription.pharmacy_id == current_user.pharmacy_id).order_by(Prescription.prescribed_on.desc()).all()


@router.post("/prescriptions", response_model=PrescriptionRead, status_code=status.HTTP_201_CREATED)
def create_prescription(payload: PrescriptionPayload, db: Session = Depends(get_db), current_user: User = Depends(require_roles("admin", "pharmacist"))):
    if payload.customer_id and not db.query(Customer).filter(Customer.id == payload.customer_id, Customer.pharmacy_id == current_user.pharmacy_id).first():
        raise HTTPException(status_code=404, detail="Customer not found in this pharmacy")
    prescription = Prescription(pharmacy_id=current_user.pharmacy_id, **payload.model_dump())
    db.add(prescription)
    db.commit()
    db.refresh(prescription)
    return prescription


@router.get("/payments", response_model=list[PaymentRead])
def list_payments(db: Session = Depends(get_db), current_user: User = Depends(require_roles("admin", "pharmacist"))):
    return db.query(PaymentRecord).filter(PaymentRecord.pharmacy_id == current_user.pharmacy_id).order_by(PaymentRecord.id.desc()).all()


@router.post("/payments", response_model=PaymentRead, status_code=status.HTTP_201_CREATED)
def record_payment(payload: PaymentPayload, db: Session = Depends(get_db), current_user: User = Depends(require_roles("admin", "pharmacist"))):
    reference = f"PAY-{current_user.pharmacy_id}-{db.query(PaymentRecord).filter(PaymentRecord.pharmacy_id == current_user.pharmacy_id).count() + 1:06d}"
    payment = PaymentRecord(pharmacy_id=current_user.pharmacy_id, reference=reference, **payload.model_dump())
    db.add(payment)
    db.add(AccountingEntry(pharmacy_id=current_user.pharmacy_id, entry_type="payment", reference=reference, description=f"Payment received by {payload.method}", debit=0, credit=payload.amount))
    db.commit()
    db.refresh(payment)
    return payment


@router.get("/exchange/listings", response_model=list[ExchangeRead])
def list_exchange_listings(db: Session = Depends(get_db), current_user: User = Depends(require_roles("admin", "pharmacist"))):
    return db.query(ExchangeListing).filter(ExchangeListing.status == "open").order_by(ExchangeListing.created_at.desc()).all()


@router.post("/exchange/listings", response_model=ExchangeRead, status_code=status.HTTP_201_CREATED)
def create_exchange_listing(payload: ExchangePayload, db: Session = Depends(get_db), current_user: User = Depends(require_roles("admin", "pharmacist"))):
    if not db.query(Medicine).filter(Medicine.id == payload.medicine_id, Medicine.pharmacy_id == current_user.pharmacy_id).first():
        raise HTTPException(status_code=404, detail="Medicine not found in this pharmacy")
    listing = ExchangeListing(pharmacy_id=current_user.pharmacy_id, **payload.model_dump())
    db.add(listing)
    db.commit()
    db.refresh(listing)
    return listing


@router.get("/integrations")
def integration_status(db: Session = Depends(get_db), current_user: User = Depends(require_roles("admin"))):
    events = db.query(IntegrationEvent).filter(IntegrationEvent.pharmacy_id == current_user.pharmacy_id).order_by(IntegrationEvent.id.desc()).limit(20).all()
    return {"available": ["tally_export", "gst_export", "whatsapp_adapter", "payment_gateway_adapter"], "events": [{"integration": event.integration, "event_type": event.event_type, "status": event.status} for event in events]}
