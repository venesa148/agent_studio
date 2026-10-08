import asyncio
import aiomysql
import ssl
from app.core.config import settings

async def alter_table():
    ssl_ctx = ssl.create_default_context()
    ssl_ctx.check_hostname = False
    ssl_ctx.verify_mode = ssl.CERT_NONE

    conn = await aiomysql.connect(
        host=settings.DB_HOST,
        user=settings.DB_USERNAME,
        password=settings.DB_PASSWORD,
        port=settings.DB_PORT,
        db=settings.DB_DATABASE,
        ssl=ssl_ctx
    )
    async with conn.cursor() as cur:
        try:
            await cur.execute("ALTER TABLE agent_specs ADD COLUMN builder_history JSON;")
            print("Successfully added builder_history column")
        except Exception as e:
            print(f"Column might already exist or error: {e}")
    await conn.commit()
    conn.close()

if __name__ == "__main__":
    asyncio.run(alter_table())
