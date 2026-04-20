from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    DATABASE_URL: str
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440
    GEMINI_API_KEY: str = ""
    ENTRY_CAM_URL: str = "http://192.168.1.100/capture"
    EXIT_CAM_URL: str = "http://192.168.1.101/capture"
    CAPTURED_IMAGES_DIR: str = "captured_images"
    ENVIRONMENT: str = "development"

    class Config:
        env_file = ".env"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
