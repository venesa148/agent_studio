import asyncio
from app.core.db import AsyncSessionLocal
from app.services.builder_service import BuilderService

async def main():
    async with AsyncSessionLocal() as db:
        prompt = "Halo, saya ingin membuat asisten toko online untuk mengecek resi pengiriman dan status paket pelanggan."
        print(f"User Prompt: {prompt}\n")
        resp = await BuilderService.build_agent_spec(db=db, prompt=prompt)
        print("--- BUILDER RESPONSE ---")
        print("Message:")
        print(resp.message)
        print("\nSpec:")
        print(resp.spec)
        print("\nNew Tools:")
        print(resp.new_tools)
        print("\nShould Commit:", resp.should_commit)

if __name__ == "__main__":
    asyncio.run(main())
