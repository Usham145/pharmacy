from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from dataclasses import dataclass

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import get_db
from app.models.entities import User

settings = get_settings()
security = HTTPBearer(auto_error=False)


def _urlsafe_b64encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _urlsafe_b64decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + padding)


def hash_password(password: str) -> str:
    salt = settings.secret_key.encode("utf-8")
    digest = hashlib.sha256(salt + password.encode("utf-8")).hexdigest()
    return f"sha256${digest}"


def verify_password(stored_password: str, provided_password: str) -> bool:
    if stored_password == provided_password:
        return True
    if stored_password.startswith("sha256$"):
        return hmac.compare_digest(stored_password, hash_password(provided_password))
    return hmac.compare_digest(stored_password, provided_password)


def create_access_token(username: str, role: str) -> str:
    now = int(time.time())
    payload = {
        "sub": username,
        "role": role,
        "iat": now,
        "exp": now + settings.access_token_expire_minutes * 60,
    }
    header = {"alg": "HS256", "typ": "JWT"}
    header_segment = _urlsafe_b64encode(json.dumps(header, separators=(",", ":")).encode("utf-8"))
    payload_segment = _urlsafe_b64encode(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    signing_input = f"{header_segment}.{payload_segment}".encode("ascii")
    signature = hmac.new(settings.secret_key.encode("utf-8"), signing_input, hashlib.sha256).digest()
    return f"{header_segment}.{payload_segment}.{_urlsafe_b64encode(signature)}"


@dataclass(frozen=True)
class TokenData:
    username: str
    role: str


def decode_access_token(token: str) -> TokenData:
    try:
        header_segment, payload_segment, signature_segment = token.split(".")
        signing_input = f"{header_segment}.{payload_segment}".encode("ascii")
        expected_signature = hmac.new(settings.secret_key.encode("utf-8"), signing_input, hashlib.sha256).digest()
        if not hmac.compare_digest(_urlsafe_b64encode(expected_signature), signature_segment):
            raise ValueError("invalid signature")
        payload = json.loads(_urlsafe_b64decode(payload_segment))
        if int(payload["exp"]) < int(time.time()):
            raise ValueError("token expired")
        return TokenData(username=payload["sub"], role=payload["role"])
    except Exception as error:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token") from error


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
    db: Session = Depends(get_db),
) -> User:
    if credentials is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    token_data = decode_access_token(credentials.credentials)
    user = db.query(User).filter(User.username == token_data.username).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    return user


def require_roles(*allowed_roles: str):
    def dependency(user: User = Depends(get_current_user)) -> User:
        if user.role not in allowed_roles:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")
        return user

    return dependency