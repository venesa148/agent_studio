import sys
import asyncio

# if sys.platform == 'win32':
#     asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.exc import OperationalError
from app.core.config import settings
from app.core.db import init_db
from app.api.router import api_router

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("app.main")

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Initializing Database tables...")
    try:
        await init_db()
        logger.info("Database initialized successfully.")
    except Exception as e:
        logger.warning(f"Database connection warning (Make sure PostgreSQL is running): {e}")
    yield
    logger.info("Shutting down Agent Studio Backend...")

app = FastAPI(
    title=settings.APP_NAME,
    version="1.0.0",
    description="FastAPI Backend for Agent Studio with Global Tools, MCP Client, and OpenAI Integration",
    lifespan=lifespan
)

# Enable CORS for Next.js frontend (default http://localhost:3000)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router)

@app.exception_handler(OperationalError)
async def database_unavailable(_: Request, exc: OperationalError):
    """Return an actionable API error when the configured database is unreachable."""
    logger.error("Database operation failed: %s", exc)
    return JSONResponse(
        status_code=503,
        content={"detail": "Database tidak dapat dihubungi. Periksa koneksi dan konfigurasi database, lalu coba lagi."},
    )

@app.get("/health", tags=["Health Check"])
async def health_check():
    return {
        "status": "online",
        "app_name": settings.APP_NAME,
        "environment": settings.ENV,
        "version": "1.0.0"
    }
