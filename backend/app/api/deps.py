from fastapi import Depends, Header, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import decode_access_token, verify_api_key
from app.db.session import get_db
from app.models.models import AdminUser, Device

_bearer = HTTPBearer(auto_error=True)


async def get_current_admin(
    creds: HTTPAuthorizationCredentials = Depends(_bearer),
    db: AsyncSession = Depends(get_db),
) -> AdminUser:
    payload = decode_access_token(creds.credentials)
    if not payload or "sub" not in payload:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid token")
    admin = (
        await db.execute(select(AdminUser).where(AdminUser.email == payload["sub"]))
    ).scalar_one_or_none()
    if admin is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "unknown admin")
    return admin


async def require_admin_role(admin: AdminUser = Depends(get_current_admin)) -> AdminUser:
    from app.models.models import AdminRole

    if admin.role != AdminRole.admin:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "admin role required")
    return admin


async def get_current_device(
    x_device_id: str = Header(...),
    x_device_key: str = Header(...),
    db: AsyncSession = Depends(get_db),
) -> Device:
    device = (
        await db.execute(select(Device).where(Device.device_id == x_device_id))
    ).scalar_one_or_none()
    if device is None or not verify_api_key(x_device_key, device.api_key_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid device credentials")
    return device
