from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import model_validator

class Settings(BaseSettings):
    APP_NAME: str = "AgentStudioBackend"
    ENV: str = "development"
    DEBUG: bool = True
    PORT: int = 8000
    HOST: str = "0.0.0.0"

    DATABASE_URL: Optional[str] = None

    # Individual DB parameters
    DB_DRIVER: str = "mysql+aiomysql"
    DB_HOST: Optional[str] = None
    DB_PORT: int = 4000
    DB_USERNAME: Optional[str] = None
    DB_PASSWORD: Optional[str] = None
    DB_DATABASE: Optional[str] = None

    OPENAI_API_KEY: str = ""
    OPENAI_DEFAULT_MODEL: str = "gpt-4o-mini"

    # LiteLLM
    LLM_BASE_URL: str = "https://litellm.pkc.pub/v1"
    LLM_MODEL: str = "glm-5.3-flash"
    LLM_API_KEY: str = ""

    API_KEY_SECRET: str = "agent_studio_secret_key_2026"
    REQUIRE_API_KEY: bool = False

    @model_validator(mode="after")
    def assemble_db_url(self) -> "Settings":
        if not self.DATABASE_URL:
            if self.DB_HOST and self.DB_USERNAME:
                driver = self.DB_DRIVER
                user = self.DB_USERNAME
                pwd = self.DB_PASSWORD or ""
                host = self.DB_HOST
                port = self.DB_PORT
                db_name = self.DB_DATABASE or ""
                self.DATABASE_URL = f"{driver}://{user}:{pwd}@{host}:{port}/{db_name}"
            else:
                self.DATABASE_URL = "postgresql+asyncpg://postgres:postgres@localhost:5432/agent_studio"
        return self

    model_config = SettingsConfigDict(
        env_file=(".env", "backend/.env"),
        env_file_encoding="utf-8",
        extra="ignore"
    )

settings = Settings()
