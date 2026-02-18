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


settings = Settings()
