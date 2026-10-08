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

if db_url.startswith("postgresql"):
    if db_url.startswith("postgresql://"):
        db_url = db_url.replace("postgresql://", "postgresql+asyncpg://", 1)
    engine_kwargs["connect_args"] = {"prepared_statement_cache_size": 0}

import ssl

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
                await conn.execute(text("ALTER TABLE tools ADD COLUMN is_active BOOLEAN DEFAULT TRUE"))
            if "auth_custody" not in cols:
                await conn.execute(text("ALTER TABLE tools ADD COLUMN auth_custody VARCHAR(100) DEFAULT 'none'"))
            if "health_status" not in cols:
                await conn.execute(text("ALTER TABLE tools ADD COLUMN health_status VARCHAR(50) DEFAULT 'healthy'"))
            if "used_by" not in cols:
                await conn.execute(text("ALTER TABLE tools ADD COLUMN used_by VARCHAR(255) DEFAULT 'All agents'"))
        
        if "conversations" in tables:
            cols = await conn.run_sync(lambda sync_conn: [c['name'] for c in inspect(sync_conn).get_columns("conversations")])
            if "agent_id" not in cols:
                await conn.execute(text("ALTER TABLE conversations ADD COLUMN agent_id VARCHAR(36) NULL"))

        if "evaluations" in tables:
            cols = await conn.run_sync(lambda sync_conn: [c['name'] for c in inspect(sync_conn).get_columns("evaluations")])
            if "score" not in cols:
                await conn.execute(text("ALTER TABLE evaluations ADD COLUMN score INTEGER NULL"))
            if "details" not in cols:
                await conn.execute(text("ALTER TABLE evaluations ADD COLUMN details JSON NULL"))

            # Pastikan MCP server lokal dan tools terdaftar di database
            import uuid
            from datetime import datetime, timezone

            local_mcp_id = None
            if "mcp_servers" in tables:
                mcp_check = await conn.execute(text("SELECT id FROM mcp_servers WHERE url = :url"), {"url": "http://localhost:8000/api/v1/mcp/local-server"})
                local_mcp_id = mcp_check.scalar()
                if not local_mcp_id:
                    local_mcp_id = str(uuid.uuid4())
                    await conn.execute(
                        text("INSERT INTO mcp_servers (id, name, url, status, created_at, updated_at) "
                             "VALUES (:id, :name, :url, 'connected', :created_at, :updated_at)"),
                        {"id": local_mcp_id, "name": "JKN Care Services MCP", "url": "http://localhost:8000/api/v1/mcp/local-server", "created_at": datetime.utcnow(), "updated_at": datetime.utcnow()}
                    )

            default_builtin_tools = [
                ("search_hospital", "Cari data rumah sakit rekanan BPJS dan ketersediaan layanan faskes", "builtin"),
                ("get_referral_status", "Cek status dan validitas nomor rujukan faskes BPJS", "builtin"),
                ("find_specialist", "Cari dokter spesialis berdasarkan poliklinik dan kota", "builtin"),
                ("check_bpjs", "Cek status kepesertaan BPJS dan eligibility layanan", "builtin"),
                ("search_web", "Pencarian web secara real-time di internet melalui DuckDuckGo", "builtin"),
                ("hospital_finder", "Cari data rumah sakit terdekat dan status faskes BPJS", "builtin"),
                ("calculator", "Evaluasi ekspresi matematika dan kalkulasi angka secara presisi", "builtin"),
                ("api_fetch", "Panggil REST API publik melalui HTTP GET atau POST", "builtin"),
                ("classify_complaint", "Triage keluhan klinis (EMERGENCY, NEED_FURTHER_CARE, INFORMATION_ONLY) dan mapping poli kandidat", "mcp"),
                ("get_participant_status", "Cek status kepesertaan JKN/BPJS dan kelayakan administrasi peserta", "mcp"),
                ("search_hospitals", "Cari direktori rumah sakit rekanan BPJS berdasarkan kota/layanan via Web API", "mcp"),
                ("search_doctors", "Cari dokter spesialis dan ketersediaan jadwal praktik di rumah sakit via Web API", "mcp"),
                ("create_appointment", "Booking janji temu/antrean faskes BPJS setelah konfirmasi eksplisit dari user via Web API", "mcp"),
                ("get_appointment", "Cek status booking janji temu dan nomor antrean pasien via Web API", "mcp"),
            ]
            for t_name, t_desc, t_source in default_builtin_tools:
                check_t = await conn.execute(text("SELECT id FROM tools WHERE name = :name"), {"name": t_name})
                if not check_t.scalar():
                    t_id = str(uuid.uuid4())
                    mcp_srv_val = local_mcp_id if t_source == "mcp" else None
                    await conn.execute(
                        text("INSERT INTO tools (id, name, description, source_type, mcp_server_id, is_active, auth_custody, health_status, used_by, created_at) "
                             "VALUES (:id, :name, :description, :source_type, :mcp_server_id, TRUE, 'none', 'healthy', 'All agents', :created_at)"),
                        {"id": t_id, "name": t_name, "description": t_desc, "source_type": t_source, "mcp_server_id": mcp_srv_val, "created_at": datetime.utcnow()}
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
