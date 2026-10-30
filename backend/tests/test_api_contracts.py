from fastapi.testclient import TestClient
import pytest

from app.main import app
from app.schemas import BatchCreate


client = TestClient(app)


def test_health_contract() -> None:
    response = client.get("/health")

    assert response.status_code in {200, 503}
    if response.status_code == 200:
        assert response.json()["status"] == "ok"


def test_login_rejects_empty_credentials_before_database_access() -> None:
    response = client.post("/api/v1/auth/login", json={"username": "", "password": ""})

    assert response.status_code == 422


def test_batch_validation_rejects_expiry_before_receipt() -> None:
    with pytest.raises(ValueError):
        BatchCreate(
            medicine_id=1,
            batch_number="B-1",
            supplier="Supplier",
            quantity=1,
            received_on="2026-02-01",
            expiry_date="2026-01-01",
        )
