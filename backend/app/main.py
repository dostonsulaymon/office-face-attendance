from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy import select

from app.api.routers import attendance, auth, devices, employees, ws
from app.core.config import get_settings
from app.core.security import hash_password
from app.db.base import Base
from app.db.session import SessionLocal, engine
from app.models.models import AdminUser, AdminRole

settings = get_settings()


async def init_db() -> None:
    # Dev-friendly bootstrap: create tables if absent. Alembic migrations are the
    # production path (see docs/BUILD_PLAN.md) and can replace this later.
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    # Bootstrap first admin if none exists.
    async with SessionLocal() as db:
        exists = (await db.execute(select(AdminUser.id).limit(1))).first()
        if not exists:
            db.add(
                AdminUser(
                    email=settings.bootstrap_admin_email,
                    password_hash=hash_password(settings.bootstrap_admin_password),
                    role=AdminRole.admin,
                )
            )
            await db.commit()


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield


app = FastAPI(title="Office Attendance API", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.dashboard_origin],
    # Dev: kiosk + dashboard are reached over localhost (incl. via adb reverse),
    # each on its own port. Allow any localhost origin so preflight for the
    # custom device headers succeeds.
    allow_origin_regex=r"http://localhost(:\d+)?",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health():
    return {"status": "ok"}


# Serve reference photos (admin-facing). Captured audit frames are NOT served here.
_media_dir = Path(settings.data_dir) / "media"
_media_dir.mkdir(parents=True, exist_ok=True)
app.mount("/media", StaticFiles(directory=str(_media_dir)), name="media")

app.include_router(auth.router)
app.include_router(employees.router)
app.include_router(devices.router)
app.include_router(attendance.router)
app.include_router(ws.router)
