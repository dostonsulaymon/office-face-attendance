from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select

from app.models.models import AttendanceSession, EventType, SessionStatus
from app.services.attendance_rules import apply_checkin, apply_checkout

T0 = datetime(2026, 7, 2, 9, 0, tzinfo=timezone.utc)


async def _count(db):
    return (await db.execute(select(func.count()).select_from(AttendanceSession))).scalar()


async def test_checkin_opens_session(db, employee):
    out = await apply_checkin(db, employee, "entrance-01", T0, 0.99)
    assert out["event_type"] == EventType.checkin
    assert out["duplicate"] is False
    assert out["session"].status == SessionStatus.open
    assert out["session"].check_in_at == T0
    assert await _count(db) == 1


async def test_repeat_checkin_is_duplicate_no_new_session(db, employee):
    await apply_checkin(db, employee, "entrance-01", T0, 0.99)
    out = await apply_checkin(db, employee, "entrance-01", T0 + timedelta(minutes=5), 0.99)
    assert out["duplicate"] is True
    assert await _count(db) == 1  # no second session created


async def test_checkout_closes_open_session(db, employee):
    await apply_checkin(db, employee, "entrance-01", T0, 0.99)
    out = await apply_checkout(db, employee, "exit-01", T0 + timedelta(hours=8), 0.97)
    assert out["anomaly"] is False
    assert out["session"].status == SessionStatus.closed
    assert out["session"].check_out_at == T0 + timedelta(hours=8)
    assert await _count(db) == 1


async def test_checkout_without_checkin_is_anomaly(db, employee):
    out = await apply_checkout(db, employee, "exit-01", T0, 0.95)
    assert out["anomaly"] is True
    assert out["session"].status == SessionStatus.anomaly
    assert out["session"].check_in_at is None


async def test_full_cycle_then_new_checkin_opens_fresh_session(db, employee):
    await apply_checkin(db, employee, "entrance-01", T0, 0.99)
    await apply_checkout(db, employee, "exit-01", T0 + timedelta(hours=4), 0.97)
    out = await apply_checkin(db, employee, "entrance-01", T0 + timedelta(hours=5), 0.98)
    assert out["duplicate"] is False
    assert out["session"].status == SessionStatus.open
    assert await _count(db) == 2  # two distinct sessions same day


async def test_checkout_closes_most_recent_open_only(db, employee):
    # An anomaly (standalone checkout) plus a real open session; checkout should
    # close the OPEN one, not touch the anomaly.
    await apply_checkout(db, employee, "exit-01", T0 - timedelta(hours=1), 0.9)  # anomaly
    await apply_checkin(db, employee, "entrance-01", T0, 0.99)                    # open
    out = await apply_checkout(db, employee, "exit-01", T0 + timedelta(hours=2), 0.96)
    assert out["session"].status == SessionStatus.closed
    anomalies = (
        await db.execute(
            select(func.count()).select_from(AttendanceSession).where(
                AttendanceSession.status == SessionStatus.anomaly
            )
        )
    ).scalar()
    assert anomalies == 1
