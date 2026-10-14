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
    engine_kwargs["connect_args"] = {
        "statement_cache_size": 0,
        "prepared_statement_cache_size": 0,
    }

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
                await conn.execute(text("ALTER TABLE agent_specs ADD COLUMN updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP"))
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
            if "status" not in cols:
                await conn.execute(text("ALTER TABLE tools ADD COLUMN status VARCHAR(50) DEFAULT 'published'"))
            if "effect" not in cols:
                await conn.execute(text("ALTER TABLE tools ADD COLUMN effect VARCHAR(50) DEFAULT 'read'"))
            if "implementation" not in cols:
                await conn.execute(text("ALTER TABLE tools ADD COLUMN implementation JSON NULL"))
            if "source_ids" not in cols:
                await conn.execute(text("ALTER TABLE tools ADD COLUMN source_ids JSON NULL"))
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

            # Seeding tools utilitas umum yang netral (bukan hardcoded BPJS)
            import uuid
            from datetime import datetime

            default_builtin_tools = [
                ("calculator", "Evaluasi ekspresi matematika dan kalkulasi angka secara presisi", "builtin"),
                ("search_web", "Pencarian web secara real-time di internet melalui DuckDuckGo", "builtin"),
            ]
            for t_name, t_desc, t_source in default_builtin_tools:
                check_t = await conn.execute(text("SELECT id FROM tools WHERE name = :name"), {"name": t_name})
                if not check_t.scalar():
                    t_id = str(uuid.uuid4())
                    await conn.execute(
                        text("INSERT INTO tools (id, name, description, source_type, is_active, auth_custody, health_status, used_by, status, effect, created_at) "
                             "VALUES (:id, :name, :description, :source_type, TRUE, 'none', 'healthy', 'All agents', 'published', 'read', :created_at)"),
                        {"id": t_id, "name": t_name, "description": t_desc, "source_type": t_source, "created_at": datetime.utcnow()}
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
