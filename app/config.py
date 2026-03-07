from pydantic import model_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    koreaexim_api_key: str = ""
    ecos_api_key: str = ""
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""
    host: str = "0.0.0.0"
    port: int = 8000
    database_url: str = "sqlite+aiosqlite:///./swap_spot.db"
    env: str = "development"
    api_timeout: int = 10

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}

    @model_validator(mode="after")
    def normalize_database_url(self) -> "Settings":
        url = self.database_url
        # Render 등에서 제공하는 postgres:// 를 postgresql+asyncpg:// 로 변환
        if url.startswith("postgres://"):
            self.database_url = url.replace("postgres://", "postgresql+asyncpg://", 1)
        elif url.startswith("postgresql://"):
            self.database_url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
        return self


settings = Settings()
