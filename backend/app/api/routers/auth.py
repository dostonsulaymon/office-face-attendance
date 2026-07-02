from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token, verify_password
from app.db.session import get_db
from app.models.models import AdminUser
from app.schemas.schemas import LoginRequest, Token

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/login", response_model=Token)
async def login(body: LoginRequest, db: AsyncSession = Depends(get_db)):
    admin = (
        await db.execute(select(AdminUser).where(AdminUser.email == body.email))
    ).scalar_one_or_none()
    if not admin or not verify_password(body.password, admin.password_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid credentials")
    return Token(access_token=create_access_token(admin.email, admin.role.value))
