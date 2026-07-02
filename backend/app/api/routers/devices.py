from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_device, require_admin_role
from app.core.security import generate_device_api_key, hash_api_key
from app.db.session import get_db
from app.models.models import Device
from app.schemas.schemas import DeviceCreate, DeviceOut, DeviceWithKey

router = APIRouter(prefix="/api/devices", tags=["devices"])


@router.post("", response_model=DeviceWithKey, dependencies=[Depends(require_admin_role)])
async def register_device(body: DeviceCreate, db: AsyncSession = Depends(get_db)):
    existing = (
        await db.execute(select(Device).where(Device.device_id == body.device_id))
    ).scalar_one_or_none()
    if existing:
        raise HTTPException(status.HTTP_409_CONFLICT, "device_id already registered")
    key = generate_device_api_key()
    device = Device(
        device_id=body.device_id, role=body.role, label=body.label, api_key_hash=hash_api_key(key)
    )
    db.add(device)
    await db.commit()
    await db.refresh(device)
    return DeviceWithKey(**DeviceOut.model_validate(device).model_dump(), api_key=key)


@router.get("", response_model=list[DeviceOut], dependencies=[Depends(require_admin_role)])
async def list_devices(db: AsyncSession = Depends(get_db)):
    rows = (await db.execute(select(Device).order_by(Device.id))).scalars().all()
    return rows


@router.post(
    "/{device_id}/rotate-key",
    response_model=DeviceWithKey,
    dependencies=[Depends(require_admin_role)],
)
async def rotate_key(device_id: str, db: AsyncSession = Depends(get_db)):
    device = (
        await db.execute(select(Device).where(Device.device_id == device_id))
    ).scalar_one_or_none()
    if not device:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "device not found")
    key = generate_device_api_key()
    device.api_key_hash = hash_api_key(key)
    await db.commit()
    await db.refresh(device)
    return DeviceWithKey(**DeviceOut.model_validate(device).model_dump(), api_key=key)


@router.post("/heartbeat", response_model=DeviceOut)
async def heartbeat(
    device: Device = Depends(get_current_device), db: AsyncSession = Depends(get_db)
):
    device.last_seen_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(device)
    return device
