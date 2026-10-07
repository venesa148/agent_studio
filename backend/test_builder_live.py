import asyncio
from app.core.db import AsyncSessionLocal
from app.services.builder_service import BuilderService

async def test_builder():
    async with AsyncSessionLocal() as session:
        prompt = "Buatkan saya agen untuk mencari dokter spesialis dan jadwal prakteknya di rumah sakit"
        res = await BuilderService.build_agent_spec(session, prompt)
        print("Message:", res.message)
        if res.spec:
            print("Spec Name:", res.spec.name)
            print("Spec Tools:", res.spec.tools)
            print("Spec Instructions Preview:", res.spec.instructions[:150])
        else:
            print("No spec created")

asyncio.run(test_builder())
