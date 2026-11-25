from __future__ import annotations

from datetime import date
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.entities import AuditLog, BatchStock, InventoryTransaction, Medicine, MedicineBarcode, User
from app.services.auth import require_roles
from app.services.barcodes import product_barcode_key
from app.services.vision import ModelUnavailableError, count_package_candidates

router = APIRouter(prefix="/vision", tags=["Inventory vision"])


class CountRequest(BaseModel):
    image_base64: str = Field(min_length=100, max_length=8_000_000)


class OpenCvReconcileRequest(CountRequest):
    medicine_id: int = Field(gt=0)
    batch_id: int = Field(gt=0)
    expected_quantity: int = Field(ge=0, le=1_000_000)
    units_per_package: int = Field(default=1, ge=1, le=1_000_000)


class BarcodeMapRequest(BaseModel):
    barcode: str = Field(min_length=1, max_length=512)
    medicine_id: int = Field(gt=0)
    units_per_package: int = Field(default=1, ge=1, le=1_000_000)


class BarcodeLookupRequest(BaseModel):
    barcode: str = Field(min_length=1, max_length=512)


class BarcodeReconcileRequest(BaseModel):
    barcode: str = Field(min_length=1, max_length=512)
    medicine_id: int = Field(gt=0)
    batch_id: int = Field(gt=0)
    expected_quantity: int = Field(ge=0, le=1_000_000)
    package_count: int = Field(gt=0, le=1_000_000)


@router.post("/count", dependencies=[Depends(require_roles("admin", "pharmacist"))])
def count_inventory_packages(payload: CountRequest) -> dict[str, object]:
    try:
        return count_package_candidates(payload.image_base64)
    except ValueError as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)) from error
    except ModelUnavailableError as error:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(error)) from error


@router.post("/opencv-reconcile")
def reconcile_opencv_inventory_count(
    payload: OpenCvReconcileRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("admin", "pharmacist")),
) -> dict[str, object]:
    if current_user.pharmacy_id is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User is not assigned to a pharmacy")

    medicine = (
        db.query(Medicine)
        .filter(Medicine.id == payload.medicine_id, Medicine.pharmacy_id == current_user.pharmacy_id)
        .first()
    )
    if not medicine:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Medicine not found in this pharmacy")
    batch = (
        db.query(BatchStock)
        .filter(BatchStock.id == payload.batch_id, BatchStock.medicine_id == medicine.id)
        .first()
    )
    if not batch:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Batch not found in this pharmacy")
    if batch.disposal_status != "active":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Only active batches can be reconciled",
        )
    if batch.quantity != payload.expected_quantity:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Batch quantity changed since scanning started. Refresh inventory and scan again.",
        )

    try:
        count_result = count_package_candidates(payload.image_base64)
    except ValueError as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)) from error
    except ModelUnavailableError as error:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(error)) from error
    if count_result["count"] < 1:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="No medicine packages were detected; inventory was not changed",
        )

    new_quantity = count_result["count"] * payload.units_per_package
    if new_quantity > 1_000_000:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Counted quantity exceeds the inventory limit",
        )

    previous_quantity = batch.quantity
    quantity_change = new_quantity - previous_quantity
    updated_rows = (
        db.query(BatchStock)
        .filter(
            BatchStock.id == batch.id,
            BatchStock.quantity == payload.expected_quantity,
            BatchStock.disposal_status == "active",
        )
        .update({BatchStock.quantity: new_quantity}, synchronize_session=False)
    )
    if updated_rows != 1:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Batch quantity changed while saving. Refresh inventory and scan again.",
        )

    if quantity_change:
        db.add(
            InventoryTransaction(
                transaction_date=date.today(),
                medicine_id=medicine.id,
                transaction_type="Stock increase" if quantity_change > 0 else "Stock decrease",
                quantity=abs(quantity_change),
                reference=batch.batch_number,
                note=(
                    f"Model-assisted package count: {count_result['count']} detected package(s) "
                    f"x {payload.units_per_package} unit(s) per package; "
                    f"quantity adjusted from {previous_quantity} to {new_quantity}"
                ),
            )
        )
    db.add(
        AuditLog(
            actor_username=current_user.username,
            pharmacy_id=current_user.pharmacy_id,
            action="opencv_inventory_reconciled",
            entity_name="batch",
            entity_id=batch.id,
            description=(
                f"Confirmed model estimate of {count_result['count']} medicine package(s) "
                f"for {medicine.name}, batch {batch.batch_number}; "
                f"quantity changed from {previous_quantity} to {new_quantity} {medicine.unit}(s)"
            ),
        )
    )
    db.commit()

    return {
        "detected_count": count_result["count"],
        "medicine_id": medicine.id,
        "medicine_name": medicine.name,
        "medicine_unit": medicine.unit,
        "batch_id": batch.id,
        "batch_number": batch.batch_number,
        "units_per_package": payload.units_per_package,
        "previous_quantity": previous_quantity,
        "new_quantity": new_quantity,
        "quantity_change": quantity_change,
        "candidates": count_result["candidates"],
    }


@router.post("/barcodes/lookup")
def lookup_medicine_barcode(
    payload: BarcodeLookupRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("admin", "pharmacist")),
) -> dict[str, object]:
    if current_user.pharmacy_id is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User is not assigned to a pharmacy")
    try:
        barcode = product_barcode_key(payload.barcode)
    except ValueError as error:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(error)) from error
    mapping = (
        db.query(MedicineBarcode, Medicine)
        .join(Medicine, MedicineBarcode.medicine_id == Medicine.id)
        .filter(
            MedicineBarcode.barcode == barcode,
            MedicineBarcode.pharmacy_id == current_user.pharmacy_id,
            Medicine.pharmacy_id == current_user.pharmacy_id,
        )
        .first()
    )
    if not mapping:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Barcode is not mapped to a medicine in this pharmacy",
        )
    barcode_record, medicine = mapping
    return {
        "medicine_id": medicine.id,
        "medicine_name": medicine.name,
        "medicine_sku": medicine.sku,
        "medicine_unit": medicine.unit,
        "barcode": barcode_record.barcode,
        "units_per_package": barcode_record.units_per_package,
    }


@router.post("/barcodes")
def map_medicine_barcode(
    payload: BarcodeMapRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("admin", "pharmacist")),
) -> dict[str, object]:
    if current_user.pharmacy_id is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User is not assigned to a pharmacy")
    try:
        barcode = product_barcode_key(payload.barcode)
    except ValueError as error:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(error)) from error
    medicine = (
        db.query(Medicine)
        .filter(Medicine.id == payload.medicine_id, Medicine.pharmacy_id == current_user.pharmacy_id)
        .first()
    )
    if not medicine:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Medicine not found in this pharmacy")
    existing = db.query(MedicineBarcode).filter(
        MedicineBarcode.barcode == barcode,
        MedicineBarcode.pharmacy_id == current_user.pharmacy_id,
    ).first()
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Barcode is already mapped")

    mapping = MedicineBarcode(
        pharmacy_id=current_user.pharmacy_id,
        medicine_id=medicine.id,
        barcode=barcode,
        units_per_package=payload.units_per_package,
    )
    db.add(mapping)
    db.flush()
    db.add(
        AuditLog(
            actor_username=current_user.username,
            pharmacy_id=current_user.pharmacy_id,
            action="medicine_barcode_mapped",
            entity_name="medicine",
            entity_id=medicine.id,
            description=(
                f"Mapped package barcode {barcode} to {medicine.name}; "
                f"{payload.units_per_package} {medicine.unit}(s) per package"
            ),
        )
    )
    db.commit()
    return {
        "barcode": mapping.barcode,
        "medicine_id": medicine.id,
        "medicine_name": medicine.name,
        "medicine_unit": medicine.unit,
        "units_per_package": mapping.units_per_package,
    }


@router.post("/barcode-reconcile")
def reconcile_barcode_inventory_count(
    payload: BarcodeReconcileRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("admin", "pharmacist")),
) -> dict[str, object]:
    if current_user.pharmacy_id is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User is not assigned to a pharmacy")
    try:
        barcode = product_barcode_key(payload.barcode)
    except ValueError as error:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(error)) from error
    mapping = (
        db.query(MedicineBarcode, Medicine)
        .join(Medicine, MedicineBarcode.medicine_id == Medicine.id)
        .filter(
            Medicine.id == payload.medicine_id,
            MedicineBarcode.barcode == barcode,
            MedicineBarcode.pharmacy_id == current_user.pharmacy_id,
            Medicine.pharmacy_id == current_user.pharmacy_id,
        )
        .first()
    )
    if not mapping:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Scanned barcode does not match the selected medicine in this pharmacy",
        )
    barcode_record, medicine = mapping

    new_quantity = payload.package_count * barcode_record.units_per_package
    if new_quantity > 1_000_000:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Counted quantity exceeds the inventory limit",
        )

    batch = (
        db.query(BatchStock)
        .filter(
            BatchStock.id == payload.batch_id,
            BatchStock.medicine_id == medicine.id,
        )
        .first()
    )
    if not batch:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Batch not found in this pharmacy",
        )
    if batch.disposal_status != "active":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Only active batches can be reconciled",
        )
    if batch.quantity != payload.expected_quantity:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Batch quantity changed since scanning started. Refresh inventory and scan again.",
        )

    previous_quantity = batch.quantity
    quantity_change = new_quantity - previous_quantity
    updated_rows = (
        db.query(BatchStock)
        .filter(
            BatchStock.id == batch.id,
            BatchStock.quantity == payload.expected_quantity,
            BatchStock.disposal_status == "active",
        )
        .update({BatchStock.quantity: new_quantity}, synchronize_session=False)
    )
    if updated_rows != 1:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Batch quantity changed while saving. Refresh inventory and scan again.",
        )

    if quantity_change:
        db.add(
            InventoryTransaction(
                transaction_date=date.today(),
                medicine_id=medicine.id,
                transaction_type="Stock increase" if quantity_change > 0 else "Stock decrease",
                quantity=abs(quantity_change),
                reference=batch.batch_number,
                note=(
                    f"Barcode-assisted count: {payload.package_count} scanned package(s) "
                    f"x {barcode_record.units_per_package} unit(s) per package; "
                    f"quantity adjusted from {previous_quantity} to {new_quantity}"
                ),
            )
        )
    db.add(
        AuditLog(
            actor_username=current_user.username,
            pharmacy_id=current_user.pharmacy_id,
            action="barcode_inventory_reconciled",
            entity_name="batch",
            entity_id=batch.id,
            description=(
                f"Confirmed scan count of {payload.package_count} barcode-identified package(s) "
                f"for {medicine.name}, batch {batch.batch_number}; "
                f"quantity changed from {previous_quantity} to {new_quantity} {medicine.unit}(s)"
            ),
        )
    )
    db.commit()

    return {
        "barcode": barcode,
        "package_count": payload.package_count,
        "medicine_id": medicine.id,
        "medicine_name": medicine.name,
        "medicine_unit": medicine.unit,
        "batch_id": batch.id,
        "batch_number": batch.batch_number,
        "units_per_package": barcode_record.units_per_package,
        "previous_quantity": previous_quantity,
        "new_quantity": new_quantity,
        "quantity_change": quantity_change,
    }
