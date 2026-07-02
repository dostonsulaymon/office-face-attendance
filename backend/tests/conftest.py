import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.db.base import Base
from app.models.models import Employee


@pytest_asyncio.fixture
async def db():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    Session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with Session() as session:
        yield session
    await engine.dispose()


@pytest_asyncio.fixture
async def employee(db):
    emp = Employee(employee_code="E1", full_name="Test User", compreface_subject_id="E1", active=True)
    db.add(emp)
    await db.commit()
    await db.refresh(emp)
    return emp
