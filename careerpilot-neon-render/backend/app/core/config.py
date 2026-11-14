from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    gemini_api_key: str = ""
    gemini_model: str = "gemini-3.5-flash-lite"
    gemini_timeout_ms: int = 30000
    # Public Greenhouse board tokens; only these configured boards are queried.
    greenhouse_board_tokens: str = "gitlab,figma,stripe,coinbase,airbnb"
    jobs_cache_seconds: int = 1800
    adzuna_app_id: str = ""
    adzuna_app_key: str = ""
    database_url: str = ""
    migration_database_url: str = ""
    jwt_secret_key: str = ""
    jwt_issuer: str = "careerpilot-api"
    jwt_audience: str = "careerpilot-web"
    access_token_minutes: int = 30
    cors_allowed_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    @property
    def cors_origins(self) -> list[str]:
        return [origin.strip().rstrip('/') for origin in self.cors_allowed_origins.split(",") if origin.strip()]

    @staticmethod
    def adapt_url(value: str) -> str:
        # Neon provides postgresql:// URLs. Select psycopg 3 explicitly.
        url = value.strip()
        if url.startswith('postgres://'):
            return 'postgresql+psycopg://' + url[len('postgres://'):]
        if url.startswith('postgresql://'):
            return 'postgresql+psycopg://' + url[len('postgresql://'):]
        return url

    @property
    def sqlalchemy_url(self) -> str:
        return self.adapt_url(self.database_url)

    @property
    def migration_url(self) -> str:
        return self.adapt_url(self.migration_database_url or self.database_url)


@lru_cache
def get_settings() -> Settings:
    return Settings()
