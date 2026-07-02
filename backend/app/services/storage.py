"""Image storage. Reference photos are stored plaintext under a restricted
volume and served (read) to admins; captured audit frames are sensitive and can
be encrypted at rest via IMAGE_ENCRYPTION_KEY (Fernet)."""
from pathlib import Path

from cryptography.fernet import Fernet

from app.core.config import get_settings

settings = get_settings()
DATA = Path(settings.data_dir)


def _fernet() -> Fernet | None:
    if settings.image_encryption_key:
        return Fernet(settings.image_encryption_key.encode())
    return None


def save_reference_photo(code: str, data: bytes, ext: str = "jpg") -> str:
    d = DATA / "media" / "employees"
    d.mkdir(parents=True, exist_ok=True)
    (d / f"{code}.{ext}").write_bytes(data)
    return f"/media/employees/{code}.{ext}"


def read_capture(ref: str) -> bytes:
    """Read a captured frame by its stored ref, decrypting if needed."""
    path = DATA / ref
    raw = path.read_bytes()
    if ref.endswith(".enc"):
        fernet = _fernet()
        if fernet is None:
            raise RuntimeError("encrypted capture but no IMAGE_ENCRYPTION_KEY set")
        return fernet.decrypt(raw)
    return raw


def save_capture(name: str, data: bytes) -> str:
    """Persist a captured audit frame; returns a storage ref (not a public URL)."""
    d = DATA / "captured"
    d.mkdir(parents=True, exist_ok=True)
    fernet = _fernet()
    if fernet:
        path = d / f"{name}.enc"
        path.write_bytes(fernet.encrypt(data))
    else:
        path = d / f"{name}.jpg"
        path.write_bytes(data)
    return str(path.relative_to(DATA))
