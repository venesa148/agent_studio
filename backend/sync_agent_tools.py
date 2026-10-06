import asyncio
import sys

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

from sqlalchemy import select
from app.core.db import AsyncSessionLocal, init_db
from app.models.agent import AgentSpecModel
from app.models.tool import ToolModel
from app.services.builder_service import BuilderService


async def sync():
    print("1. Inisialisasi dan sinkronisasi katalog tools ke database...")
    await init_db()

    async with AsyncSessionLocal() as session:
        # Cek tools di database
        tools_res = await session.execute(select(ToolModel).where(ToolModel.is_active == True))
        db_tools = list(tools_res.scalars().all())
        valid_tool_names = {t.name for t in db_tools}
        print(f"-> Total tools aktif di database: {len(db_tools)}")
        for t in db_tools:
            print(f"   * [{t.source_type}] {t.name} - {t.description}")

        # Cek agents di database
        agents_res = await session.execute(select(AgentSpecModel))
        agents = list(agents_res.scalars().all())
        print(f"\n2. Memvalidasi & menyinkronkan {len(agents)} agents dengan tools database...")

        updated_count = 0
        for agent in agents:
            old_tools = agent.tools or []
            # Jika agent memiliki instruksi/prompt khusus, sesuaikan tools berdasarkan katalog database
            combined_text = f"{agent.name} {agent.description or ''} {agent.instructions or ''}"
            new_tools = await BuilderService._select_tools_from_db(session, combined_text)

            # Jika tidak ada yang match tapi ada tools lama yang valid di DB, simpan yang valid saja
            if not new_tools and old_tools:
                new_tools = [t for t in old_tools if t in valid_tool_names]

            if old_tools != new_tools:
                agent.tools = new_tools
                updated_count += 1
                print(f"   [SYNCED] {agent.name}:")
                print(f"      Sebelum: {old_tools}")
                print(f"      Sesudah: {new_tools}")
            else:
                print(f"   [OK] {agent.name}: {agent.tools}")

        await session.commit()
        print(f"\nSelesai! {updated_count} agents berhasil disinkronkan dengan tools database.")


if __name__ == "__main__":
    asyncio.run(sync())
