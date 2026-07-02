import csv
import io
import uuid
from datetime import date as date_cls
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from fastapi.responses import Response, StreamingResponse
from openpyxl import Workbook
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_device, require_admin_role
from app.core.config import get_settings
from app.db.session import get_db
from app.models.models import (
    AttendanceRawEvent,
    AttendanceSession,
    Device,
    DeviceRole,
    Employee,
    EventType,
    SessionStatus,
)
from app.schemas.schemas import (
    AttendanceEventResult,
    RawEventOut,
    SessionOut,
    TodayRow,
    TodaySummary,
)
from app.services import cache, compreface, liveness, storage
from app.services.attendance_rules import apply_checkin, apply_checkout
from app.services.broadcast import broadcaster

settings = get_settings()
router = APIRouter(prefix="/api/attendance", tags=["attendance"])


def _log_raw(db, **kw) -> None:
    db.add(AttendanceRawEvent(**kw))


@router.post("/event", response_model=AttendanceEventResult)
async def attendance_event(
    image: UploadFile = File(...),
    device: Device = Depends(get_current_device),
    db: AsyncSession = Depends(get_db),
):
    if await cache.rate_limited(device.device_id):
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "rate limit exceeded")

    now = datetime.now(timezone.utc)
    event_type = EventType.checkin if device.role == DeviceRole.CHECK_IN else EventType.checkout
    data = await image.read()
    if not data:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "empty image")

    # 1. Server-side liveness — never trusted from the client.
    passed, live_score = await liveness.is_live(data)
    if not passed:
        ref = storage.save_capture(str(uuid.uuid4()), data)
        _log_raw(
            db, employee_id=None, device_id=device.device_id, event_type=event_type,
            matched=False, confidence=None, liveness_score=live_score,
            reject_reason="liveness", image_ref=ref,
        )
        await db.commit()
        return AttendanceEventResult(
            matched=False, liveness_score=live_score,
            message="Liveness check failed — please try again",
        )

    # 2. Recognition.
    subject, similarity = await compreface.best_match(data)
    matched_emp = None
    if subject:
        matched_emp = (
            await db.execute(
                select(Employee).where(
                    Employee.compreface_subject_id == subject, Employee.active.is_(True)
                )
            )
        ).scalar_one_or_none()

    if not matched_emp or similarity < settings.recognition_confidence_threshold:
        ref = storage.save_capture(str(uuid.uuid4()), data)
        reason = "low_confidence" if matched_emp else "unrecognized"
        _log_raw(
            db, employee_id=matched_emp.id if matched_emp else None,
            device_id=device.device_id, event_type=event_type, matched=False,
            confidence=similarity, liveness_score=live_score, reject_reason=reason, image_ref=ref,
        )
        await db.commit()
        return AttendanceEventResult(
            matched=False, confidence=similarity, liveness_score=live_score,
            message="Face not recognized",
        )

    # 3. Cooldown — swallow rapid re-triggers of the same person on this device.
    if await cache.in_cooldown(device.device_id, matched_emp.id, settings.cooldown_seconds):
        return AttendanceEventResult(
            matched=True, employee_id=matched_emp.id, employee_name=matched_emp.full_name,
            photo_url=matched_emp.photo_url, confidence=similarity, liveness_score=live_score,
            message="Already registered a moment ago", timestamp=now,
        )

    # 4. Business rules.
    if event_type == EventType.checkin:
        outcome = await apply_checkin(db, matched_emp, device.device_id, now, similarity)
    else:
        outcome = await apply_checkout(db, matched_emp, device.device_id, now, similarity)

    # 5. Audit trail + device heartbeat.
    ref = storage.save_capture(str(uuid.uuid4()), data)
    _log_raw(
        db, employee_id=matched_emp.id, device_id=device.device_id,
        event_type=outcome["event_type"], matched=True, confidence=similarity,
        liveness_score=live_score, reject_reason=None, image_ref=ref,
    )
    device.last_seen_at = now
    await db.commit()

    # 6. Push to dashboards.
    await broadcaster.publish(
        {
            "type": outcome["event_type"].value,
            "employee_id": matched_emp.id,
            "employee_name": matched_emp.full_name,
            "department": matched_emp.department,
            "photo_url": matched_emp.photo_url,
            "timestamp": now.isoformat(),
            "anomaly": outcome["anomaly"],
            "duplicate": outcome["duplicate"],
        }
    )
    return AttendanceEventResult(
        matched=True, event_type=outcome["event_type"], employee_id=matched_emp.id,
        employee_name=matched_emp.full_name, photo_url=matched_emp.photo_url,
        confidence=similarity, liveness_score=live_score, message=outcome["message"], timestamp=now,
    )


@router.get("/today", response_model=TodaySummary, dependencies=[Depends(require_admin_role)])
async def today(db: AsyncSession = Depends(get_db)):
    today_date = datetime.now(timezone.utc).date()
    stmt = (
        select(AttendanceSession, Employee)
        .join(Employee, Employee.id == AttendanceSession.employee_id)
        .where(AttendanceSession.date == today_date)
        .order_by(desc(AttendanceSession.check_in_at))
    )
    rows, currently_in = [], 0
    for s, e in (await db.execute(stmt)).all():
        rows.append(
            TodayRow(
                employee_id=e.id, full_name=e.full_name, department=e.department,
                check_in_at=s.check_in_at, check_out_at=s.check_out_at, status=s.status,
            )
        )
        if s.status == SessionStatus.open:
            currently_in += 1
    return TodaySummary(currently_in=currently_in, rows=rows)


def _history_stmt(employee_id, date_from, date_to):
    stmt = select(AttendanceSession).order_by(desc(AttendanceSession.date))
    if employee_id:
        stmt = stmt.where(AttendanceSession.employee_id == employee_id)
    if date_from:
        stmt = stmt.where(AttendanceSession.date >= date_from)
    if date_to:
        stmt = stmt.where(AttendanceSession.date <= date_to)
    return stmt


@router.get("/history", response_model=list[SessionOut], dependencies=[Depends(require_admin_role)])
async def history(
    employee_id: int | None = None,
    date_from: date_cls | None = Query(None, alias="from"),
    date_to: date_cls | None = Query(None, alias="to"),
    db: AsyncSession = Depends(get_db),
):
    rows = (await db.execute(_history_stmt(employee_id, date_from, date_to))).scalars().all()
    return rows


@router.get(
    "/review", response_model=list[RawEventOut], dependencies=[Depends(require_admin_role)]
)
async def review_queue(
    only_rejected: bool = True, limit: int = 100, db: AsyncSession = Depends(get_db)
):
    """Unmatched / liveness-failed / low-confidence attempts, newest first."""
    stmt = select(AttendanceRawEvent).order_by(desc(AttendanceRawEvent.created_at)).limit(limit)
    if only_rejected:
        stmt = stmt.where(AttendanceRawEvent.matched.is_(False))
    return (await db.execute(stmt)).scalars().all()


@router.get("/capture/{event_id}", dependencies=[Depends(require_admin_role)])
async def capture_image(event_id: int, db: AsyncSession = Depends(get_db)):
    ev = await db.get(AttendanceRawEvent, event_id)
    if not ev or not ev.image_ref:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "no capture for this event")
    try:
        data = storage.read_capture(ev.image_ref)
    except FileNotFoundError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "capture file missing (retention?)")
    return Response(content=data, media_type="image/jpeg")


@router.get("/export", dependencies=[Depends(require_admin_role)])
async def export(
    fmt: str = Query("csv", pattern="^(csv|xlsx)$", alias="format"),
    employee_id: int | None = None,
    date_from: date_cls | None = Query(None, alias="from"),
    date_to: date_cls | None = Query(None, alias="to"),
    db: AsyncSession = Depends(get_db),
):
    stmt = (
        select(AttendanceSession, Employee)
        .join(Employee, Employee.id == AttendanceSession.employee_id)
        .order_by(desc(AttendanceSession.date))
    )
    if employee_id:
        stmt = stmt.where(AttendanceSession.employee_id == employee_id)
    if date_from:
        stmt = stmt.where(AttendanceSession.date >= date_from)
    if date_to:
        stmt = stmt.where(AttendanceSession.date <= date_to)

    header = ["Date", "Employee", "Department", "Check-in", "Check-out", "Status"]
    records = []
    for s, e in (await db.execute(stmt)).all():
        records.append([
            s.date.isoformat(),
            e.full_name,
            e.department or "",
            s.check_in_at.isoformat() if s.check_in_at else "",
            s.check_out_at.isoformat() if s.check_out_at else "",
            s.status.value,
        ])

    if fmt == "csv":
        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow(header)
        writer.writerows(records)
        return StreamingResponse(
            iter([buf.getvalue()]),
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=attendance.csv"},
        )

    wb = Workbook()
    ws = wb.active
    ws.title = "Attendance"
    ws.append(header)
    for row in records:
        ws.append(row)
    out = io.BytesIO()
    wb.save(out)
    out.seek(0)
    return StreamingResponse(
        out,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=attendance.xlsx"},
    )
