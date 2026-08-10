from functools import lru_cache
import os
from pathlib import Path

from pydantic import BaseModel, Field
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[3] / ".env")


class Settings(BaseModel):
    app_name: str = "Pharmacy Inventory & Expiry Management System"
    api_prefix: str = "/api/v1"
    database_url: str = Field(default_factory=lambda: os.getenv("DATABASE_URL", "sqlite:///./pharmacy.db"))
    secret_key: str = os.getenv("SECRET_KEY", "dev-pharmacy-secret-key")
    access_token_expire_minutes: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "480"))
    cors_origins: list[str] = Field(
        default_factory=lambda: [
            origin.strip()
            for origin in os.getenv(
                "CORS_ORIGINS",
                "http://localhost:5173,http://127.0.0.1:5173,http://localhost:4173,http://127.0.0.1:4173",
            ).split(",")
            if origin.strip()
        ]
    )
    near_expiry_days: int = int(os.getenv("NEAR_EXPIRY_DAYS", "90"))
    admin_alert_email: str = os.getenv("ADMIN_ALERT_EMAIL", "")
    pharmacist_alert_email: str = os.getenv("PHARMACIST_ALERT_EMAIL", "")
    smtp_host: str = os.getenv("SMTP_HOST", "")
    smtp_port: int = int(os.getenv("SMTP_PORT", "587"))
    smtp_username: str = os.getenv("SMTP_USERNAME", "")
    smtp_password: str = os.getenv("SMTP_PASSWORD", "")
    smtp_from_email: str = os.getenv("SMTP_FROM_EMAIL", "")
    smtp_use_tls: bool = os.getenv("SMTP_USE_TLS", "true").lower() == "true"
    procurement_unit_price: float = float(os.getenv("PROCUREMENT_UNIT_PRICE", "50"))
    forecast_horizon_days: tuple[int, int, int] = (30, 60, 90)
    demo_admin_username: str = "admin"
    demo_admin_password: str = "admin123"
    demo_pharmacist_username: str = "pharmacist"
    demo_pharmacist_password: str = "pharmacist123"
    demo_viewer_username: str = "viewer"
    demo_viewer_password: str = "viewer123"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
