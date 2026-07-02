from __future__ import annotations

import enum
from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    String,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin


class DeviceRole(str, enum.Enum):
    CHECK_IN = "CHECK_IN"
    CHECK_OUT = "CHECK_OUT"


class EventType(str, enum.Enum):
    checkin = "checkin"
    checkout = "checkout"


class SessionStatus(str, enum.Enum):
    open = "open"
    closed = "closed"
    anomaly = "anomaly"


class AdminRole(str, enum.Enum):
    admin = "admin"
    viewer = "viewer"


class Employee(Base, TimestampMixin):
    __tablename__ = "employees"

    id: Mapped[int] = mapped_column(primary_key=True)
    employee_code: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    full_name: Mapped[str] = mapped_column(String(255))
    department: Mapped[str | None] = mapped_column(String(128), nullable=True)
    position: Mapped[str | None] = mapped_column(String(128), nullable=True)
    photo_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    # CompreFace subject id we enroll faces under (kept == employee_code for clarity)
    compreface_subject_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    sessions: Mapped[list[AttendanceSession]] = relationship(back_populates="employee")


class Device(Base):
    __tablename__ = "devices"

    id: Mapped[int] = mapped_column(primary_key=True)
    device_id: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    role: Mapped[DeviceRole] = mapped_column(Enum(DeviceRole, name="device_role"))
    label: Mapped[str | None] = mapped_column(String(255), nullable=True)
    api_key_hash: Mapped[str] = mapped_column(String(255))
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class AttendanceSession(Base):
    __tablename__ = "attendance_sessions"

    id: Mapped[int] = mapped_column(primary_key=True)
    employee_id: Mapped[int] = mapped_column(ForeignKey("employees.id", ondelete="CASCADE"), index=True)
    date: Mapped[date] = mapped_column(Date, index=True)
    status: Mapped[SessionStatus] = mapped_column(
        Enum(SessionStatus, name="session_status"), default=SessionStatus.open, index=True
    )

    check_in_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    check_in_device_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    check_in_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)

    check_out_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    check_out_device_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    check_out_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)

    employee: Mapped[Employee] = relationship(back_populates="sessions")


class AttendanceRawEvent(Base):
    """Full audit log of every kiosk submission, matched or not."""

    __tablename__ = "attendance_raw_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    employee_id: Mapped[int | None] = mapped_column(
        ForeignKey("employees.id", ondelete="SET NULL"), nullable=True, index=True
    )
    device_id: Mapped[str] = mapped_column(String(128), index=True)
    event_type: Mapped[EventType] = mapped_column(Enum(EventType, name="event_type"))
    matched: Mapped[bool] = mapped_column(Boolean, default=False)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    liveness_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    reject_reason: Mapped[str | None] = mapped_column(String(64), nullable=True)
    image_ref: Mapped[str | None] = mapped_column(String(512), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )


class AdminUser(Base, TimestampMixin):
    __tablename__ = "admin_users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[AdminRole] = mapped_column(Enum(AdminRole, name="admin_role"), default=AdminRole.admin)
