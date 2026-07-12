from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "Commodity Agent"
    debug: bool = False
    secret_key: str = "change-me-in-production"
    database_url: str = "postgresql://commodity:commodity@localhost:5432/commodity_agent"
    storage_path: str = "./data/storage"
    cors_origins: str = "http://localhost:3000"
    session_cookie_name: str = "session_id"
    session_max_age_seconds: int = 86400 * 7
    cookie_secure: bool = False
    cookie_samesite: str = "lax"
    admin_email: str = "admin@localhost"
    admin_password: str = "changeme"

    # AI / OpenAI
    openai_api_key: str = ""
    openai_default_model: str = "gpt-4o-mini"
    openai_fallback_model: str = "gpt-4o"
    ai_max_retries: int = 2
    ai_provider: str = "openai"  # openai | mock
    email_provider: str = "mock"  # mock | gmail | graph


settings = Settings()
