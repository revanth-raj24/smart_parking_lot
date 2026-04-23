from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    DATABASE_URL: str
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440
    OPENROUTER_API_KEY: str = ""

    # ESP32 device IPs are NOT configured here.
    # Devices register themselves via POST /api/devices/register on every boot.
    # The backend resolves the current IP from the `devices` table at runtime.

    CAPTURED_IMAGES_DIR: str = "captured_images"
    ENVIRONMENT: str = "development"
    USER_APP_ORIGIN: str = "http://localhost:5173"
    ADMIN_APP_ORIGIN: str = "http://localhost:5174"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
