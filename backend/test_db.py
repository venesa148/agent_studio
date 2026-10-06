import asyncio
import aiomysql
import ssl
from app.core.config import settings
import sys

if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

async def setup_test_db():
    try:
        ssl_ctx = ssl.create_default_context()
        ssl_ctx.check_hostname = False
        ssl_ctx.verify_mode = ssl.CERT_NONE

        conn = await aiomysql.connect(
            host=settings.DB_HOST,
            user=settings.DB_USERNAME,
            password=settings.DB_PASSWORD,
            port=settings.DB_PORT,
            db="sys",
            ssl=ssl_ctx
        )
        async with conn.cursor() as cur:
            await cur.execute("CREATE DATABASE IF NOT EXISTS agent_studio_test")
        await conn.commit()
        print("Database agent_studio_test created successfully!")
        conn.close()
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(setup_test_db())
