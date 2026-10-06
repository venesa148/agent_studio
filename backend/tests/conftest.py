import pytest
import asyncio
from typing import AsyncGenerator
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from app.main import app
from app.core.db import Base, get_db

from sqlalchemy.pool import StaticPool

# Use SQLite in-memory engine for fast automated testing
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

test_engine = create_async_engine(
    TEST_DATABASE_URL,
    echo=False,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = async_sessionmaker(bind=test_engine, class_=AsyncSession, expire_on_commit=False)

@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()

@pytest.fixture(autouse=True)
async def prepare_database():
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        import uuid
        from sqlalchemy import text
        default_builtin_tools = [
            ("search_hospital", "Cari data rumah sakit rekanan BPJS dan ketersediaan layanan faskes", "builtin"),
            ("get_referral_status", "Cek status dan validitas nomor rujukan faskes BPJS", "builtin"),
            ("find_specialist", "Cari dokter spesialis berdasarkan poliklinik dan kota", "builtin"),
            ("check_bpjs", "Cek status kepesertaan BPJS dan eligibility layanan", "builtin"),
            ("search_web", "Search the web for real-time information", "builtin"),
            ("hospital_finder", "Cari data rumah sakit terdekat dan status faskes BPJS", "builtin"),
        ]
        from datetime import datetime, timezone
        for t_name, t_desc, t_source in default_builtin_tools:
            t_id = str(uuid.uuid4())
            await conn.execute(
                text("INSERT INTO tools (id, name, description, source_type, is_active, auth_custody, health_status, used_by, created_at) "
                     "VALUES (:id, :name, :description, :source_type, 1, 'none', 'healthy', 'All agents', :created_at)"),
                {"id": t_id, "name": t_name, "description": t_desc, "source_type": t_source, "created_at": datetime.now(timezone.utc)}
            )
    yield
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
    async with TestingSessionLocal() as session:
        yield session

app.dependency_overrides[get_db] = override_get_db

@pytest.fixture
async def async_client() -> AsyncGenerator[AsyncClient, None]:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client
