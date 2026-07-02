"""Core check-in / check-out session-matching business rules.

Kept deliberately explicit — these are the subtle bits (Slice 8 tests target
them). All functions operate on an AsyncSession and flush but do NOT commit; the
caller owns the transaction.
"""
from datetime import datetime

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models import AttendanceSession, EventType, SessionStatus


async def _open_session(db: AsyncSession, employee_id: int) -> AttendanceSession | None:
    return (
        (
            await db.execute(
                select(AttendanceSession)
                .where(
                    AttendanceSession.employee_id == employee_id,
                    AttendanceSession.status == SessionStatus.open,
                )
                .order_by(desc(AttendanceSession.check_in_at))
            )
        )
        .scalars()
        .first()
    )


async def apply_checkin(
    db: AsyncSession, employee, device_id: str, now: datetime, confidence: float | None
) -> dict:
    open_s = await _open_session(db, employee.id)
    if open_s:
        # Already checked in and not yet out -> duplicate / no-op.
        return {
            "event_type": EventType.checkin,
            "session": open_s,
            "duplicate": True,
            "anomaly": False,
            "message": f"Already checked in at {open_s.check_in_at:%H:%M}",
        }
    session = AttendanceSession(
        employee_id=employee.id,
        date=now.date(),
        status=SessionStatus.open,
        check_in_at=now,
        check_in_device_id=device_id,
        check_in_confidence=confidence,
    )
    db.add(session)
    await db.flush()
    return {
        "event_type": EventType.checkin,
        "session": session,
        "duplicate": False,
        "anomaly": False,
        "message": f"Welcome, {employee.full_name}",
    }


async def apply_checkout(
    db: AsyncSession, employee, device_id: str, now: datetime, confidence: float | None
) -> dict:
    open_s = await _open_session(db, employee.id)
    if not open_s:
        # No open session -> record a standalone, anomalous check-out for audit.
        session = AttendanceSession(
            employee_id=employee.id,
            date=now.date(),
            status=SessionStatus.anomaly,
            check_out_at=now,
            check_out_device_id=device_id,
            check_out_confidence=confidence,
        )
        db.add(session)
        await db.flush()
        return {
            "event_type": EventType.checkout,
            "session": session,
            "duplicate": False,
            "anomaly": True,
            "message": "Check-out recorded without a prior check-in — flagged for review",
        }
    open_s.check_out_at = now
    open_s.check_out_device_id = device_id
    open_s.check_out_confidence = confidence
    open_s.status = SessionStatus.closed
    await db.flush()
    return {
        "event_type": EventType.checkout,
        "session": open_s,
        "duplicate": False,
        "anomaly": False,
        "message": f"Goodbye, {employee.full_name}",
    }
