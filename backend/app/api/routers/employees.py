from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_admin_role
from app.db.session import get_db
from app.models.models import Employee
from app.schemas.schemas import EmployeeOut, EmployeeUpdate
from app.services import compreface, storage

router = APIRouter(prefix="/api/employees", tags=["employees"])


@router.post("", response_model=EmployeeOut, dependencies=[Depends(require_admin_role)])
async def enroll(
    employee_code: str = Form(...),
    full_name: str = Form(...),
    department: str | None = Form(None),
    position: str | None = Form(None),
    photos: list[UploadFile] = File(...),
    db: AsyncSession = Depends(get_db),
):
    if not 1 <= len(photos) <= 3:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "provide 1-3 reference photos")

    dup = (
        await db.execute(select(Employee).where(Employee.employee_code == employee_code))
    ).scalar_one_or_none()
    if dup:
        raise HTTPException(status.HTTP_409_CONFLICT, "employee_code already exists")

    subject = employee_code
    photo_bytes = [await p.read() for p in photos]

    # Enroll every reference photo under the CompreFace subject. On any failure,
    # purge the subject so we never leave half-registered biometric data behind.
    try:
        for i, data in enumerate(photo_bytes):
            await compreface.add_face(subject, data, filename=f"{subject}_{i}.jpg")
    except compreface.CompreFaceError as exc:
        await compreface.delete_subject(subject)
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, f"enrollment failed: {exc}")

    photo_url = storage.save_reference_photo(subject, photo_bytes[0])
    emp = Employee(
        employee_code=employee_code,
        full_name=full_name,
        department=department,
        position=position,
        compreface_subject_id=subject,
        photo_url=photo_url,
        active=True,
    )
    db.add(emp)
    await db.commit()
    await db.refresh(emp)
    return emp


@router.get("", response_model=list[EmployeeOut], dependencies=[Depends(require_admin_role)])
async def list_employees(q: str | None = None, db: AsyncSession = Depends(get_db)):
    stmt = select(Employee).order_by(Employee.full_name)
    if q:
        like = f"%{q}%"
        stmt = stmt.where(
            or_(
                Employee.full_name.ilike(like),
                Employee.employee_code.ilike(like),
                Employee.department.ilike(like),
            )
        )
    return (await db.execute(stmt)).scalars().all()


@router.patch("/{employee_id}", response_model=EmployeeOut, dependencies=[Depends(require_admin_role)])
async def update_employee(
    employee_id: int, body: EmployeeUpdate, db: AsyncSession = Depends(get_db)
):
    emp = await db.get(Employee, employee_id)
    if not emp:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "employee not found")
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(emp, field, value)
    await db.commit()
    await db.refresh(emp)
    return emp


@router.delete("/{employee_id}", status_code=status.HTTP_204_NO_CONTENT,
               dependencies=[Depends(require_admin_role)])
async def delete_employee(employee_id: int, db: AsyncSession = Depends(get_db)):
    """Right-to-erasure: purge CompreFace embeddings AND the DB row."""
    emp = await db.get(Employee, employee_id)
    if not emp:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "employee not found")
    if emp.compreface_subject_id:
        await compreface.delete_subject(emp.compreface_subject_id)
    await db.delete(emp)
    await db.commit()
