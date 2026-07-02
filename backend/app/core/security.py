import secrets
from datetime import datetime, timedelta, timezone

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import get_settings

settings = get_settings()
_pwd = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    return _pwd.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return _pwd.verify(plain, hashed)


def create_access_token(subject: str, role: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.jwt_access_token_expire_minutes)
    payload = {"sub": subject, "role": role, "exp": expire}
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> dict | None:
    try:
        return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    except JWTError:
        return None


def generate_device_api_key() -> str:
    """Return a fresh opaque device API key (store only its hash)."""
    return secrets.token_urlsafe(32)


def hash_api_key(api_key: str) -> str:
    return _pwd.hash(api_key)


def verify_api_key(plain: str, hashed: str) -> bool:
    return _pwd.verify(plain, hashed)
