import os
import uvicorn
from pathlib import Path
from dotenv import load_dotenv

# Muat .env dari direktori yang sama dengan run.py (backend/)
load_dotenv(Path(__file__).parent / ".env")

from app.core.config import settings

if __name__ == "__main__":
    port = int(os.getenv("PORT", str(settings.PORT or 8000)))
    print(f"[Agent Studio] Starting backend on http://0.0.0.0:{port}")
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=port,
        reload=settings.DEBUG
    )
