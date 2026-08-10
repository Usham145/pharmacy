from __future__ import annotations

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import inspect, text
from sqlalchemy.orm import Session

from app.api.routes import router
from app.core.config import get_settings
from app.db.base import Base
from app.db.session import engine, get_db
from app.models import entities  # noqa: F401  # ensure model registration
from app.services.seed import seed_demo_data

settings = get_settings()
app = FastAPI(title=settings.app_name, version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router, prefix=settings.api_prefix)


@app.on_event("startup")
def on_startup() -> None:
    Base.metadata.create_all(bind=engine)
    # Lightweight compatibility migration for existing demonstration databases.
    columns = {column["name"] for column in inspect(engine).get_columns("users")}
    with engine.begin() as connection:
        if "email" not in columns:
            connection.execute(text("ALTER TABLE users ADD COLUMN email VARCHAR(128)"))
        if "pharmacy_id" not in columns:
            connection.execute(text("ALTER TABLE users ADD COLUMN pharmacy_id INTEGER"))
    batch_columns = {column["name"] for column in inspect(engine).get_columns("batch_stocks")}
    with engine.begin() as connection:
        if "unit_price" not in batch_columns:
            connection.execute(text("ALTER TABLE batch_stocks ADD COLUMN unit_price FLOAT NOT NULL DEFAULT 50"))
        if "disposal_status" not in batch_columns:
            connection.execute(text("ALTER TABLE batch_stocks ADD COLUMN disposal_status VARCHAR(32) NOT NULL DEFAULT 'active'"))
        if "disposal_method" not in batch_columns:
            connection.execute(text("ALTER TABLE batch_stocks ADD COLUMN disposal_method VARCHAR(64)"))
        if "disposal_reference" not in batch_columns:
            connection.execute(text("ALTER TABLE batch_stocks ADD COLUMN disposal_reference VARCHAR(64)"))
        if "disposed_on" not in batch_columns:
            connection.execute(text("ALTER TABLE batch_stocks ADD COLUMN disposed_on DATE"))
    medicine_columns = {column["name"] for column in inspect(engine).get_columns("medicines")}
    if "pharmacy_id" not in medicine_columns:
        with engine.begin() as connection:
            connection.execute(text("ALTER TABLE medicines ADD COLUMN pharmacy_id INTEGER"))
    db = next(get_db())
    try:
        seed_demo_data(db)
    finally:
        db.close()


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
