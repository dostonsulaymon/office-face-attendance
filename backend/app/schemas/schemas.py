from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, EmailStr

from app.models.models import DeviceRole, EventType, SessionStatus


# --- auth ---
class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


# --- employees ---
class EmployeeCreate(BaseModel):
    employee_code: str
    full_name: str
    department: str | None = None
    position: str | None = None


class EmployeeUpdate(BaseModel):
    full_name: str | None = None
    department: str | None = None
    position: str | None = None
    active: bool | None = None


class EmployeeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    employee_code: str
    full_name: str
    department: str | None
    position: str | None
    photo_url: str | None
    active: bool
    created_at: datetime


# --- devices ---
class DeviceCreate(BaseModel):
    device_id: str
    role: DeviceRole
    label: str | None = None


class DeviceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    device_id: str
    role: DeviceRole
    label: str | None
    last_seen_at: datetime | None


class DeviceWithKey(DeviceOut):
    api_key: str  # returned ONCE on create / rotate


# --- attendance ---
class AttendanceEventResult(BaseModel):
    matched: bool
    event_type: EventType | None = None
    employee_id: int | None = None
    employee_name: str | None = None
    photo_url: str | None = None
    confidence: float | None = None
    liveness_score: float | None = None
    message: str
    timestamp: datetime | None = None


class SessionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    employee_id: int
    date: date
    status: SessionStatus
    check_in_at: datetime | None
    check_out_at: datetime | None


class TodayRow(BaseModel):
    employee_id: int
    full_name: str
    department: str | None
    check_in_at: datetime | None
    check_out_at: datetime | None
    status: SessionStatus


class TodaySummary(BaseModel):
    currently_in: int
    rows: list[TodayRow]


class RawEventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    employee_id: int | None
    device_id: str
    event_type: EventType
    matched: bool
    confidence: float | None
    liveness_score: float | None
    reject_reason: str | None
    image_ref: str | None
    created_at: datetime
