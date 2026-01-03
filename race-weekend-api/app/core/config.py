from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    ENV: str = "dev"
    APP_NAME: str = "Race Weekend Checklist API"

    DATABASE_URL: str = "postgresql+psycopg2://app:app@localhost:5432/race_weekend"
    REDIS_URL: str = "redis://localhost:6379/0"

    JWT_SECRET: str = "change-me"
    JWT_ALG: str = "HS256"
    JWT_EXPIRES_MINUTES: int = 60

    RATE_LIMIT_PER_MINUTE: int = 60
    CACHE_TTL_SECONDS: int = 30

settings = Settings()
