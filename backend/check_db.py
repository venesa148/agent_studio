import asyncio
import sys
from sqlalchemy import inspect
from app.core.db import engine, init_db

if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

async def main():
    await init_db()
    async with engine.connect() as conn:
        tables = await conn.run_sync(lambda sync_conn: inspect(sync_conn).get_table_names())
        print("Existing tables:", tables)
        for t in tables:
            cols = await conn.run_sync(lambda sync_conn, table_name=t: inspect(sync_conn).get_columns(table_name))
            col_names = [c['name'] for c in cols]
            print(f"Table {t} columns:", col_names)

if __name__ == "__main__":
    asyncio.run(main())
