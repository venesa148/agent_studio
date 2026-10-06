from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from app.core.config import settings

class Base(DeclarativeBase):
    pass

# Ensure database URL is compatible with async drivers
db_url = settings.DATABASE_URL
engine_kwargs = {"echo": settings.DEBUG, "future": True}

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
