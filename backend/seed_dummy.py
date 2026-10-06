import sys
import asyncio

if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

from sqlalchemy.ext.asyncio import AsyncSession
from app.core.db import engine, init_db, AsyncSessionLocal
from app.models.agent import AgentSpecModel
from app.models.mcp import MCPServerModel
from app.models.tool import ToolModel
import datetime

async def seed():
    print("Initializing DB...")
    await init_db()
    print("DB initialized. Seeding dummy data...")
    
    async with AsyncSessionLocal() as session:
        # Check if already seeded
        # Seed MCPServer
        mcp_server = MCPServerModel(
            name="github-mcp",
            url="http://localhost:8080/mcp"
        )
        session.add(mcp_server)

        # Seed Tool
        tool = ToolModel(
            name="search_web",
            description="Search the web for real-time information",
            input_schema={"type": "object", "properties": {"query": {"type": "string"}}}
        )
        session.add(tool)

        # Seed Agent
        agent = AgentSpecModel(
            name="Customer Service Agent",
            description="Agent for handling customer inquiries",
            instructions="You are a helpful customer service agent.",
            model="gpt-4o-mini",
            mcp_servers=["github-mcp"],
            tools=["search_web"]
        )
        session.add(agent)

        await session.commit()
        print("Seeding complete!")

if __name__ == "__main__":
    asyncio.run(seed())
