from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from app.core.config import settings

class Base(DeclarativeBase):
    pass

# Ensure database URL is compatible with async drivers
db_url = settings.DATABASE_URL
engine_kwargs = {
    "echo": settings.DEBUG,
    "future": True,
    "pool_pre_ping": True,
    "pool_recycle": 300,
}

if db_url.startswith("postgresql://"):
    db_url = db_url.replace("postgresql://", "postgresql+asyncpg://", 1)
elif db_url.startswith("mysql://"):
    db_url = db_url.replace("mysql://", "mysql+aiomysql://", 1)

import ssl

if "tidbcloud.com" in db_url:
    ssl_context = ssl.create_default_context()
    ssl_context.check_hostname = False
    ssl_context.verify_mode = ssl.CERT_NONE
    engine_kwargs["connect_args"] = {"ssl": ssl_context}

engine = create_async_engine(
    db_url,
    **engine_kwargs
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)

async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        from sqlalchemy import inspect, text
        tables = await conn.run_sync(lambda sync_conn: inspect(sync_conn).get_table_names())
        if "agent_specs" in tables:
            cols = await conn.run_sync(lambda sync_conn: [c['name'] for c in inspect(sync_conn).get_columns("agent_specs")])
            if "status" not in cols:
                await conn.execute(text("ALTER TABLE agent_specs ADD COLUMN status VARCHAR(50) DEFAULT 'active'"))
            if "updated_at" not in cols:
                await conn.execute(text("ALTER TABLE agent_specs ADD COLUMN updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"))
        if "tools" in tables:
            cols = await conn.run_sync(lambda sync_conn: [c['name'] for c in inspect(sync_conn).get_columns("tools")])
            if "source_type" not in cols:
                await conn.execute(text("ALTER TABLE tools ADD COLUMN source_type VARCHAR(50) DEFAULT 'mcp'"))
            if "mcp_server_id" not in cols:
                await conn.execute(text("ALTER TABLE tools ADD COLUMN mcp_server_id VARCHAR(36) NULL"))
            if "input_schema" not in cols:
                await conn.execute(text("ALTER TABLE tools ADD COLUMN input_schema JSON NULL"))
            if "is_active" not in cols:
                await conn.execute(text("ALTER TABLE tools ADD COLUMN is_active BOOLEAN DEFAULT 1"))
            if "auth_custody" not in cols:
                await conn.execute(text("ALTER TABLE tools ADD COLUMN auth_custody VARCHAR(100) DEFAULT 'none'"))
            if "health_status" not in cols:
                await conn.execute(text("ALTER TABLE tools ADD COLUMN health_status VARCHAR(50) DEFAULT 'healthy'"))
            if "used_by" not in cols:
                await conn.execute(text("ALTER TABLE tools ADD COLUMN used_by VARCHAR(255) DEFAULT 'All agents'"))

            # Pastikan tools built-in standar tersimpan di database
            import uuid
            default_builtin_tools = [
                ("search_hospital", "Cari data rumah sakit rekanan BPJS dan ketersediaan layanan faskes", "builtin"),
                ("get_referral_status", "Cek status dan validitas nomor rujukan faskes BPJS", "builtin"),
                ("find_specialist", "Cari dokter spesialis berdasarkan poliklinik dan kota", "builtin"),
                ("check_bpjs", "Cek status kepesertaan BPJS dan eligibility layanan", "builtin"),
                ("search_web", "Pencarian web secara real-time di internet melalui DuckDuckGo", "builtin"),
                ("hospital_finder", "Cari data rumah sakit terdekat dan status faskes BPJS", "builtin"),
                ("calculator", "Evaluasi ekspresi matematika dan kalkulasi angka secara presisi", "builtin"),
                ("api_fetch", "Panggil REST API publik melalui HTTP GET atau POST", "builtin"),
            ]
            from datetime import datetime, timezone
            for t_name, t_desc, t_source in default_builtin_tools:
                check_t = await conn.execute(text("SELECT id FROM tools WHERE name = :name"), {"name": t_name})
                if not check_t.scalar():
                    t_id = str(uuid.uuid4())
                    await conn.execute(
                        text("INSERT INTO tools (id, name, description, source_type, is_active, auth_custody, health_status, used_by, created_at) "
                             "VALUES (:id, :name, :description, :source_type, 1, 'none', 'healthy', 'All agents', :created_at)"),
                        {"id": t_id, "name": t_name, "description": t_desc, "source_type": t_source, "created_at": datetime.now(timezone.utc)}
                    )


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
