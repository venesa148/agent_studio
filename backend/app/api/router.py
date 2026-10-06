from fastapi import APIRouter
from app.api.v1.tools import router as tools_router
from app.api.v1.mcp import router as mcp_router
from app.api.v1.builder import router as builder_router
from app.api.v1.agent import router as agent_router
from app.api.v1.trace import router as trace_router
from app.api.v1.chatbot import router as chat_router

api_router = APIRouter(prefix="/api/v1")

api_router.include_router(tools_router)
api_router.include_router(mcp_router)
api_router.include_router(builder_router)
api_router.include_router(trace_router)
api_router.include_router(agent_router)
api_router.include_router(chat_router)
