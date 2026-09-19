"""Application settings loaded from environment variables / .env file."""
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=BASE_DIR.parent / ".env", extra="ignore")

    APP_NAME: str = "SAHAYATA"
    APP_VERSION: str = "1.0.0"
    ENVIRONMENT: str = "dev"  # dev | production

    # --- Database ---
    DATABASE_URL: str = f"sqlite:///{BASE_DIR / 'data' / 'sahayata.db'}"

    # --- Security ---
    SECRET_KEY: str = ""
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 12
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # --- HTTP ---
    CORS_ORIGINS: str = "http://localhost:5173,http://127.0.0.1:5173"
    RATE_LIMIT_DEFAULT: str = "120/minute"
    RATE_LIMIT_AUTH: str = "10/minute"

    # --- Storage (local driver by default; s3 driver interface provided) ---
    STORAGE_DRIVER: str = "local"  # local | s3
    UPLOAD_DIR: Path = BASE_DIR / "data" / "uploads"
    MAX_IMAGE_MB: int = 10
    MAX_VIDEO_MB: int = 50
    MAX_AUDIO_MB: int = 15
    PUBLIC_BASE_URL: str = ""  # optional, for absolute media URLs
    S3_BUCKET: str = ""
    S3_ENDPOINT_URL: str = ""
    S3_ACCESS_KEY: str = ""
    S3_SECRET_KEY: str = ""

    # --- AI (all optional; system degrades gracefully) ---
    AI_TEXT_ENABLED: bool = True
    AI_VISION_PROVIDER: str = "none"  # none | openai
    OPENAI_API_KEY: str = ""
    OPENAI_BASE_URL: str = "https://api.openai.com/v1"
    OPENAI_VISION_MODEL: str = "gpt-4o-mini"
    ENABLE_LOCAL_STT: bool = False  # requires faster-whisper installed separately

    # --- Geo / clustering defaults ---
    DEFAULT_CENTER_LAT: float = 23.3441  # Ranchi (demo region)
    DEFAULT_CENTER_LNG: float = 85.3096
    CLUSTER_RADIUS_M_DEFAULT: int = 150
    CLUSTER_TEXT_SIMILARITY_THRESHOLD: float = 0.62
    CLUSTER_TIME_WINDOW_DAYS: int = 30
    PUBLIC_COORD_JITTER_M: int = 150

    # --- Bootstrap admin ---
    ADMIN_EMAIL: str = "admin@sahayata.gov.in"
    ADMIN_PASSWORD: str = ""

    @property
    def is_sqlite(self) -> bool:
        return self.DATABASE_URL.startswith("sqlite")

    @property
    def is_postgres(self) -> bool:
        return self.DATABASE_URL.startswith(("postgresql", "postgres"))

    @property
    def cors_origins(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
