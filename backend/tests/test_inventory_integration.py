from __future__ import annotations

import base64
from collections.abc import Iterator
from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api import routes as api_routes
from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models.entities import Pharmacy, Supplier, User
from app.services.auth import create_access_token, hash_password


@pytest.fixture
def inventory_client() -> Iterator[TestClient]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    test_sessions = sessionmaker(bind=engine, autoflush=False, autocommit=False)

    with test_sessions() as db:
        pharmacy = Pharmacy(name="Inventory Integration Pharmacy")
        db.add(pharmacy)
        db.flush()
        db.add(User(
            username="inventory-admin",
            full_name="Inventory Admin",
            role="admin",
            password=hash_password("test-password"),
            pharmacy_id=pharmacy.id,
        ))
        db.commit()
        token = create_access_token("inventory-admin", "admin")

    def override_get_db():
        with test_sessions() as db:
            yield db

    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app, headers={"Authorization": f"Bearer {token}"})
    try:
        yield client
    finally:
        client.close()
        app.dependency_overrides.pop(get_db, None)
        engine.dispose()


def create_stock(
    client: TestClient,
    quantity: int = 20,
    sku: str = "INT-001",
    medicine_name: str = "Integration Medicine",
    batch_number: str = "INT-BATCH-001",
) -> tuple[int, str]:
    medicine_response = client.post(
        "/api/v1/medicines",
        json={
            "name": medicine_name,
            "sku": sku,
            "category": "Test",
            "unit": "tablet",
        },
    )
    assert medicine_response.status_code == 201
    medicine_id = medicine_response.json()["id"]

    batch_response = client.post(
        "/api/v1/batches",
        json={
            "medicine_id": medicine_id,
            "batch_number": batch_number,
            "supplier": "Integration Supplier",
            "quantity": quantity,
            "unit_price": 5,
            "received_on": date.today().isoformat(),
            "expiry_date": (date.today() + timedelta(days=365)).isoformat(),
            "location": "Main Store",
        },
    )
    assert batch_response.status_code == 201
    return medicine_id, batch_response.json()["batch_number"]


def test_authenticated_camera_count_endpoint_returns_reviewable_candidates(
    inventory_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "app.api.vision.count_package_candidates",
        lambda _: {
            "count": 2,
            "image_width": 640,
            "image_height": 480,
            "candidates": [
                {"x": 50, "y": 80, "width": 70, "height": 120, "confidence": 0.91},
                {"x": 400, "y": 100, "width": 160, "height": 70, "confidence": 0.86},
            ],
            "method": "yolov8n_onnx",
        },
    )

    response = inventory_client.post(
        "/api/v1/vision/count",
        json={"image_base64": base64.b64encode(b"x" * 100).decode("ascii")},
    )

    assert response.status_code == 200
    assert response.json()["count"] == 2
    assert response.json()["method"] == "yolov8n_onnx"


def test_confirmed_model_estimate_updates_selected_batch(
    inventory_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    medicine_id, _ = create_stock(inventory_client, quantity=20)
    batch = inventory_client.get("/api/v1/batches").json()[0]
    monkeypatch.setattr(
        "app.api.vision.count_package_candidates",
        lambda _: {
            "count": 2,
            "image_width": 640,
            "image_height": 480,
            "candidates": [
                {"x": 50, "y": 80, "width": 70, "height": 120, "confidence": 0.91},
                {"x": 400, "y": 100, "width": 160, "height": 70, "confidence": 0.86},
            ],
            "method": "yolov8n_onnx",
        },
    )

    response = inventory_client.post(
        "/api/v1/vision/opencv-reconcile",
        json={
            "image_base64": base64.b64encode(b"x" * 100).decode("ascii"),
            "medicine_id": medicine_id,
            "batch_id": batch["id"],
            "expected_quantity": batch["quantity"],
            "units_per_package": 1,
        },
    )

    assert response.status_code == 200
    assert response.json()["detected_count"] == 2
    assert response.json()["new_quantity"] == 2
    assert response.json()["quantity_change"] == -18
    updated_batch = inventory_client.get("/api/v1/batches").json()[0]
    assert updated_batch["quantity"] == 2
    transactions = inventory_client.get("/api/v1/transactions").json()
    adjustment = next(item for item in transactions if item["transaction_type"] == "Stock decrease")
    assert adjustment["quantity"] == 18
    assert "Model-assisted package count: 2 detected package(s)" in adjustment["note"]


def test_model_reconcile_rejects_empty_estimate_and_stale_batch(
    inventory_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    medicine_id, _ = create_stock(inventory_client, quantity=20)
    batch = inventory_client.get("/api/v1/batches").json()[0]
    image_base64 = base64.b64encode(b"x" * 100).decode("ascii")
    monkeypatch.setattr(
        "app.api.vision.count_package_candidates",
        lambda _: {
            "count": 0,
            "image_width": 640,
            "image_height": 480,
            "candidates": [],
            "method": "yolov8n_onnx",
        },
    )
    request_body = {
        "image_base64": image_base64,
        "medicine_id": medicine_id,
        "batch_id": batch["id"],
        "expected_quantity": batch["quantity"],
        "units_per_package": 1,
    }

    empty_response = inventory_client.post("/api/v1/vision/opencv-reconcile", json=request_body)
    assert empty_response.status_code == 422
    assert inventory_client.get("/api/v1/batches").json()[0]["quantity"] == 20

    request_body["expected_quantity"] = 19
    stale_response = inventory_client.post("/api/v1/vision/opencv-reconcile", json=request_body)

    assert stale_response.status_code == 409
    assert inventory_client.get("/api/v1/batches").json()[0]["quantity"] == 20


def test_confirmed_barcode_count_reconciles_batch_and_rejects_stale_quantity(inventory_client: TestClient) -> None:
    medicine_id, _ = create_stock(inventory_client, quantity=20)
    batch = inventory_client.get("/api/v1/batches").json()[0]
    first_barcode = "8901234567890"
    second_barcode = "8901234567891"
    first_mapping = inventory_client.post(
        "/api/v1/vision/barcodes",
        json={"barcode": first_barcode, "medicine_id": medicine_id, "units_per_package": 15},
    )
    assert first_mapping.status_code == 200
    assert inventory_client.post(
        "/api/v1/vision/barcodes/lookup",
        json={"barcode": first_barcode},
    ).json()["medicine_id"] == medicine_id
    duplicate_mapping = inventory_client.post(
        "/api/v1/vision/barcodes",
        json={"barcode": first_barcode, "medicine_id": medicine_id, "units_per_package": 1},
    )
    assert duplicate_mapping.status_code == 409
    mismatched_medicine = inventory_client.post("/api/v1/vision/barcode-reconcile", json={
        "barcode": first_barcode,
        "medicine_id": medicine_id + 100,
        "batch_id": batch["id"],
        "expected_quantity": batch["quantity"],
        "package_count": 2,
    })
    assert mismatched_medicine.status_code == 409

    increase_response = inventory_client.post("/api/v1/vision/barcode-reconcile", json={
        "barcode": first_barcode,
        "medicine_id": medicine_id,
        "batch_id": batch["id"],
        "expected_quantity": batch["quantity"],
        "package_count": 2,
    })
    assert increase_response.status_code == 200
    assert increase_response.json()["package_count"] == 2
    assert increase_response.json()["new_quantity"] == 30
    assert increase_response.json()["quantity_change"] == 10
    assert inventory_client.get("/api/v1/batches").json()[0]["quantity"] == 30

    second_mapping = inventory_client.post(
        "/api/v1/vision/barcodes",
        json={"barcode": second_barcode, "medicine_id": medicine_id, "units_per_package": 5},
    )
    assert second_mapping.status_code == 200
    decrease_response = inventory_client.post("/api/v1/vision/barcode-reconcile", json={
        "barcode": second_barcode,
        "medicine_id": medicine_id,
        "batch_id": batch["id"],
        "expected_quantity": 30,
        "package_count": 2,
    })
    assert decrease_response.status_code == 200
    assert decrease_response.json()["new_quantity"] == 10
    assert decrease_response.json()["quantity_change"] == -20
    assert inventory_client.get("/api/v1/batches").json()[0]["quantity"] == 10

    stale_response = inventory_client.post("/api/v1/vision/barcode-reconcile", json={
        "barcode": first_barcode,
        "medicine_id": medicine_id,
        "batch_id": batch["id"],
        "expected_quantity": 30,
        "package_count": 2,
    })
    assert stale_response.status_code == 409
    assert inventory_client.get("/api/v1/batches").json()[0]["quantity"] == 10
    transaction_types = {item["transaction_type"] for item in inventory_client.get("/api/v1/transactions").json()}
    assert {"Stock increase", "Stock decrease"} <= transaction_types
    assert any(item["action"] == "barcode_inventory_reconciled" for item in inventory_client.get("/api/v1/activity").json())


def test_receipt_fefo_and_department_use_refresh_inventory_views(inventory_client: TestClient) -> None:
    medicine_id, _ = create_stock(inventory_client, quantity=20)

    transaction_response = inventory_client.get("/api/v1/transactions")
    assert transaction_response.status_code == 200
    assert [item["transaction_type"] for item in transaction_response.json()] == ["Receipt"]
    assert inventory_client.get("/api/v1/dashboard/summary").json()["total_units"] == 20
    assert inventory_client.get("/api/v1/dashboard/insights").json()["total_transactions"] == 1

    dispense_response = inventory_client.post(
        "/api/v1/dispense",
        json={"lookup": "INT-001", "quantity": 5, "department": "Ward A"},
    )
    assert dispense_response.status_code == 200
    assert dispense_response.json()["quantity"] == 15
    assert dispense_response.json()["available_quantity"] == 15
    assert inventory_client.get("/api/v1/dashboard/summary").json()["total_units"] == 20
    department_stock = inventory_client.get("/api/v1/department-inventory").json()
    assert department_stock[0]["medicine_id"] == medicine_id
    assert department_stock[0]["quantity"] == 5

    use_response = inventory_client.post(
        "/api/v1/department-inventory/use",
        json={
            "department": "Ward A",
            "medicine_id": medicine_id,
            "batch_number": "INT-BATCH-001",
            "quantity": 2,
        },
    )
    assert use_response.status_code == 200
    assert use_response.json()["quantity"] == 3
    summary = inventory_client.get("/api/v1/dashboard/summary").json()
    assert summary["monthly_consumption"] == 2
    assert summary["total_units"] == 18
    transaction_types = {
        transaction["transaction_type"]
        for transaction in inventory_client.get("/api/v1/transactions").json()
    }
    assert transaction_types == {"Receipt", "Dispense", "Department use"}


def test_certified_pickup_links_and_collects_equipment_and_expired_batches(inventory_client: TestClient) -> None:
    equipment_response = inventory_client.post(
        "/api/v1/waste/equipment",
        json={
            "name": "Expired sharps container",
            "asset_number": "WASTE-001",
            "equipment_type": "Sharps container",
            "waste_category": "Sharps / needles",
            "quantity": 1,
            "unit": "container",
            "condition": "contaminated",
            "location": "Quarantine",
        },
    )
    assert equipment_response.status_code == 201
    equipment_id = equipment_response.json()["id"]

    medicine_response = inventory_client.post(
        "/api/v1/medicines",
        json={"name": "Expired test medicine", "sku": "EXP-001", "category": "Test", "unit": "tablet"},
    )
    assert medicine_response.status_code == 201
    batch_response = inventory_client.post(
        "/api/v1/batches",
        json={
            "medicine_id": medicine_response.json()["id"],
            "batch_number": "EXP-BATCH-001",
            "supplier": "Integration Supplier",
            "quantity": 4,
            "unit_price": 5,
            "received_on": (date.today() - timedelta(days=30)).isoformat(),
            "expiry_date": (date.today() - timedelta(days=1)).isoformat(),
            "location": "Quarantine",
        },
    )
    assert batch_response.status_code == 201
    batch_id = batch_response.json()["id"]

    pickup_response = inventory_client.post(
        "/api/v1/waste/pickups",
        json={
            "vendor_name": "Licensed Test Collector",
            "vendor_contact": "Licence TEST-123",
            "scheduled_date": date.today().isoformat(),
            "waste_category": "Mixed biomedical waste",
            "equipment_ids": [equipment_id],
            "batch_ids": [batch_id],
        },
    )
    assert pickup_response.status_code == 201
    pickup = pickup_response.json()
    assert pickup["equipment_ids"] == [equipment_id]
    assert pickup["batch_ids"] == [batch_id]
    assert "EXP-BATCH-001" in pickup["item_summary"]
    assert inventory_client.get("/api/v1/batches").json()[0]["disposal_status"] == "collection_requested"

    collected_response = inventory_client.put(
        f"/api/v1/waste/pickups/{pickup['id']}",
        json={"status": "collected", "manifest_number": "MANIFEST-123"},
    )
    assert collected_response.status_code == 200
    assert collected_response.json()["equipment_ids"] == [equipment_id]
    assert collected_response.json()["batch_ids"] == [batch_id]
    assert inventory_client.get("/api/v1/waste/equipment").json()[0]["waste_status"] == "collected"
    assert inventory_client.get("/api/v1/batches").json()[0]["disposal_status"] == "disposed"

    destroyed_response = inventory_client.put(
        f"/api/v1/waste/pickups/{pickup['id']}",
        json={"status": "destroyed", "certificate_reference": "CERT-123"},
    )
    assert destroyed_response.status_code == 200
    assert destroyed_response.json()["certificate_reference"] == "CERT-123"


def test_dashboard_low_stock_counts_department_units(inventory_client: TestClient) -> None:
    create_stock(inventory_client, quantity=10)
    dispense_response = inventory_client.post(
        "/api/v1/dispense",
        json={"lookup": "INT-001", "quantity": 6, "department": "Ward A"},
    )
    assert dispense_response.status_code == 200

    summary = inventory_client.get("/api/v1/dashboard/summary").json()
    assert summary["total_units"] == 10
    assert summary["low_stock_items"] == 0
    alerts = inventory_client.get("/api/v1/alerts").json()
    assert not any(alert["alert_type"] == "low_stock" for alert in alerts)


def test_fefo_consumes_earliest_expiry_across_multiple_batches(inventory_client: TestClient) -> None:
    medicine_id, _ = create_stock(inventory_client, quantity=5)
    earlier_batch_response = inventory_client.post(
        "/api/v1/batches",
        json={
            "medicine_id": medicine_id,
            "batch_number": "INT-BATCH-EARLY",
            "supplier": "Integration Supplier",
            "quantity": 5,
            "unit_price": 5,
            "received_on": date.today().isoformat(),
            "expiry_date": (date.today() + timedelta(days=30)).isoformat(),
            "location": "Main Store",
        },
    )
    assert earlier_batch_response.status_code == 201

    dispense_response = inventory_client.post(
        "/api/v1/dispense",
        json={"lookup": "INT-001", "quantity": 7, "department": "Ward A"},
    )
    assert dispense_response.status_code == 200
    assert dispense_response.json()["available_quantity"] == 3
    batches = {
        batch["batch_number"]: batch["quantity"]
        for batch in inventory_client.get("/api/v1/batches").json()
    }
    assert batches == {"INT-BATCH-EARLY": 0, "INT-BATCH-001": 3}
    dispense_transaction = next(
        transaction
        for transaction in inventory_client.get("/api/v1/transactions").json()
        if transaction["transaction_type"] == "Dispense"
    )
    assert "INT-BATCH-EARLY:5" in dispense_transaction["reference"]
    assert "INT-BATCH-001:2" in dispense_transaction["reference"]


def test_batch_quantity_adjustments_and_delete_are_audited(inventory_client: TestClient) -> None:
    medicine_id, batch_number = create_stock(inventory_client, quantity=12)
    batch = inventory_client.get("/api/v1/batches").json()[0]

    update_response = inventory_client.put(
        f"/api/v1/batches/{batch['id']}",
        json={"quantity": 9},
    )
    assert update_response.status_code == 200
    assert inventory_client.get("/api/v1/dashboard/summary").json()["total_units"] == 9

    transaction_types = [
        transaction["transaction_type"]
        for transaction in inventory_client.get("/api/v1/transactions").json()
    ]
    assert set(transaction_types) == {"Receipt", "Stock decrease"}

    delete_response = inventory_client.delete(f"/api/v1/batches/{batch['id']}")
    assert delete_response.status_code == 200
    assert inventory_client.get("/api/v1/dashboard/summary").json()["total_units"] == 0
    transactions = inventory_client.get("/api/v1/transactions").json()
    assert any(transaction["reference"] == batch_number for transaction in transactions)
    assert any(transaction["transaction_type"] == "Stock decrease" for transaction in transactions)

    medicine_delete_response = inventory_client.delete(f"/api/v1/medicines/{medicine_id}")
    assert medicine_delete_response.status_code == 409
    assert "Deactivate it instead" in medicine_delete_response.json()["detail"]


def test_sales_use_fefo_stock_and_update_consumption(inventory_client: TestClient) -> None:
    create_stock(inventory_client, quantity=10)

    sale_response = inventory_client.post(
        "/api/v1/sales",
        json={
            "lookup": "INT-001",
            "quantity": 3,
            "buyer_name": "Test Buyer",
        },
    )
    assert sale_response.status_code == 201
    assert inventory_client.get("/api/v1/dashboard/summary").json()["total_units"] == 7
    assert inventory_client.get("/api/v1/dashboard/summary").json()["monthly_consumption"] == 3
    assert any(
        transaction["transaction_type"] == "Sale"
        for transaction in inventory_client.get("/api/v1/transactions").json()
    )


def test_multi_medicine_sale_creates_one_itemized_invoice(inventory_client: TestClient) -> None:
    create_stock(inventory_client, quantity=10)
    create_stock(
        inventory_client,
        quantity=8,
        sku="INT-002",
        medicine_name="Second Integration Medicine",
        batch_number="INT-BATCH-002",
    )

    sale_response = inventory_client.post(
        "/api/v1/sales",
        json={
            "items": [
                {"lookup": "INT-001", "quantity": 3},
                {"lookup": "INT-002", "quantity": 4},
            ],
            "buyer_name": "Test Buyer",
        },
    )

    assert sale_response.status_code == 201
    invoice = sale_response.json()
    assert invoice["total_amount"] == 35
    assert [line["sku"] for line in invoice["items"]] == ["INT-001", "INT-002"]
    assert [line["quantity"] for line in invoice["items"]] == [3, 4]
    listed_invoice = inventory_client.get("/api/v1/sales").json()[0]
    assert listed_invoice["invoice_number"] == invoice["invoice_number"]
    assert len(listed_invoice["items"]) == 2
    assert inventory_client.get("/api/v1/dashboard/summary").json()["total_units"] == 11
    assert inventory_client.get("/api/v1/dashboard/summary").json()["monthly_consumption"] == 7
    accounting = inventory_client.get("/api/v1/extensions/accounting-summary").json()
    assert accounting["sales_total"] == 35
    assert accounting["outstanding"] == 35
    assert accounting["gst_total"] == 0


def test_multi_medicine_sale_does_not_partially_decrement_stock(inventory_client: TestClient) -> None:
    create_stock(inventory_client, quantity=10)
    create_stock(
        inventory_client,
        quantity=5,
        sku="INT-002",
        medicine_name="Second Integration Medicine",
        batch_number="INT-BATCH-002",
    )

    sale_response = inventory_client.post(
        "/api/v1/sales",
        json={
            "items": [
                {"lookup": "INT-001", "quantity": 2},
                {"lookup": "INT-002", "quantity": 6},
            ],
            "buyer_name": "Test Buyer",
        },
    )

    assert sale_response.status_code == 400
    assert inventory_client.get("/api/v1/dashboard/summary").json()["total_units"] == 15
    assert inventory_client.get("/api/v1/sales").json() == []


def test_gst_profile_is_saved_as_metadata_and_rate_is_bounded(inventory_client: TestClient) -> None:
    profile_response = inventory_client.put(
        "/api/v1/extensions/tax-profile",
        json={
            "gstin": "29ABCDE1234F1Z5",
            "legal_name": "Integration Pharmacy",
            "default_gst_rate": 18,
            "state_code": "29",
        },
    )
    assert profile_response.status_code == 200
    assert profile_response.json()["default_gst_rate"] == 18
    assert inventory_client.get("/api/v1/extensions/tax-profile").json()["gstin"] == "29ABCDE1234F1Z5"

    invalid_rate_response = inventory_client.put(
        "/api/v1/extensions/tax-profile",
        json={"default_gst_rate": 101},
    )
    assert invalid_rate_response.status_code == 422
    assert inventory_client.get("/api/v1/extensions/tax-profile").json()["default_gst_rate"] == 18


def test_customer_sales_and_invoice_payments_are_linked(inventory_client: TestClient) -> None:
    create_stock(inventory_client, quantity=10)
    customer_response = inventory_client.post(
        "/api/v1/extensions/customers",
        json={"name": "Demo Customer", "phone": "555-0101"},
    )
    assert customer_response.status_code == 201
    customer = customer_response.json()

    sale_response = inventory_client.post(
        "/api/v1/sales",
        json={
            "lookup": "INT-001",
            "quantity": 2,
            "buyer_name": "Walk-in label",
            "customer_id": customer["id"],
        },
    )
    assert sale_response.status_code == 201
    invoice = sale_response.json()
    assert invoice["customer_id"] == customer["id"]
    assert invoice["buyer_name"] == customer["name"]
    assert inventory_client.get("/api/v1/sales").json()[0]["invoice_number"] == invoice["invoice_number"]

    payment_response = inventory_client.post(
        "/api/v1/extensions/payments",
        json={"amount": 5, "method": "cash", "invoice_number": invoice["invoice_number"]},
    )
    assert payment_response.status_code == 201
    assert inventory_client.get("/api/v1/extensions/accounting-summary").json()["outstanding"] == 5

    overpayment_response = inventory_client.post(
        "/api/v1/extensions/payments",
        json={"amount": 6, "method": "cash", "invoice_number": invoice["invoice_number"]},
    )
    assert overpayment_response.status_code == 400
    assert inventory_client.get("/api/v1/extensions/accounting-summary").json()["outstanding"] == 5

    unallocated_response = inventory_client.post(
        "/api/v1/extensions/payments",
        json={"amount": 20, "method": "cash"},
    )
    assert unallocated_response.status_code == 201
    assert inventory_client.get("/api/v1/extensions/accounting-summary").json()["outstanding"] == 5


def test_inactive_medicine_cannot_receive_or_dispense(inventory_client: TestClient) -> None:
    medicine_id, _ = create_stock(inventory_client, quantity=5)
    update_response = inventory_client.put(
        f"/api/v1/medicines/{medicine_id}",
        json={"active": False},
    )
    assert update_response.status_code == 200

    dispense_response = inventory_client.post(
        "/api/v1/dispense",
        json={"lookup": "INT-001", "quantity": 1, "department": "Ward A"},
    )
    assert dispense_response.status_code == 409
    assert inventory_client.get("/api/v1/dashboard/summary").json()["total_units"] == 0

    receipt_response = inventory_client.post(
        "/api/v1/batches",
        json={
            "medicine_id": medicine_id,
            "batch_number": "INT-BATCH-002",
            "supplier": "Integration Supplier",
            "quantity": 1,
            "received_on": date.today().isoformat(),
            "expiry_date": (date.today() + timedelta(days=365)).isoformat(),
            "location": "Main Store",
        },
    )
    assert receipt_response.status_code == 409


def test_expired_collection_removes_department_stock_and_records_full_quantity(inventory_client: TestClient) -> None:
    medicine_id, _ = create_stock(inventory_client, quantity=20)
    dispense_response = inventory_client.post(
        "/api/v1/dispense",
        json={"lookup": "INT-001", "quantity": 5, "department": "Ward A"},
    )
    assert dispense_response.status_code == 200
    batch = inventory_client.get("/api/v1/batches").json()[0]

    expired_on = date.today() - timedelta(days=1)
    update_response = inventory_client.put(
        f"/api/v1/batches/{batch['id']}",
        json={
            "received_on": (expired_on - timedelta(days=365)).isoformat(),
            "expiry_date": expired_on.isoformat(),
        },
    )
    assert update_response.status_code == 200

    use_response = inventory_client.post(
        "/api/v1/department-inventory/use",
        json={
            "department": "Ward A",
            "medicine_id": medicine_id,
            "batch_number": "INT-BATCH-001",
            "quantity": 1,
        },
    )
    assert use_response.status_code == 409

    collection_response = inventory_client.post(
        f"/api/v1/batches/{batch['id']}/collection-request",
        json={"method": "Licensed disposal", "pickup_contact": "Waste team"},
    )
    assert collection_response.status_code == 200
    confirmation_response = inventory_client.post(
        f"/api/v1/batches/{batch['id']}/confirm-collection",
        json={"handover_reference": "MANIFEST-001"},
    )
    assert confirmation_response.status_code == 200
    assert inventory_client.get("/api/v1/department-inventory").json() == []
    assert inventory_client.get("/api/v1/dashboard/summary").json()["total_units"] == 0
    disposal = next(
        transaction
        for transaction in inventory_client.get("/api/v1/transactions").json()
        if transaction["transaction_type"] == "Expiry disposal"
    )
    assert disposal["quantity"] == 20


def test_procurement_scan_round_robins_active_medicine_suppliers(
    inventory_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db_generator = app.dependency_overrides[get_db]()
    db = next(db_generator)
    try:
        db.add(Supplier(
            company_name="Waste Collector",
            contact_person="Waste Contact",
            phone="9000000000",
            email="waste@example.test",
            gst_number="WASTE-TEST",
            address="Test",
            waste_vendor=True,
        ))
        db.add_all([
            Supplier(
                company_name="Supplier A",
                contact_person="Contact A",
                phone="9000000001",
                email="supplier-a@example.test",
                gst_number="SUPPLIER-A",
                address="Test",
            ),
            Supplier(
                company_name="Supplier B",
                contact_person="Contact B",
                phone="9000000002",
                email="supplier-b@example.test",
                gst_number="SUPPLIER-B",
                address="Test",
            ),
        ])
        db.commit()
    finally:
        db_generator.close()

    monkeypatch.setattr(api_routes, "send_procurement_email", lambda **kwargs: False)
    for index in range(3):
        response = inventory_client.post(
            "/api/v1/medicines",
            json={
                "name": f"Procurement Medicine {index}",
                "sku": f"PROC-{index}",
                "category": "Test",
                "unit": "tablet",
            },
        )
        assert response.status_code == 201

    scan_response = inventory_client.post("/api/v1/procurement/scan")
    assert scan_response.status_code == 200
    requests = scan_response.json()
    assert [(request["supplier_name"], request["supplier_email"]) for request in requests] == [
        ("Supplier A", "supplier-a@example.test"),
        ("Supplier B", "supplier-b@example.test"),
        ("Supplier A", "supplier-a@example.test"),
    ]
    assert all(request["status"] == "pending_review" for request in requests)
    assert inventory_client.post("/api/v1/procurement/scan").json() == []
