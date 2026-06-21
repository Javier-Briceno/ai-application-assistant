from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    anthropic_api_key: str
    openai_api_key: str
    serpapi_key: str

    db_host: str = "127.0.0.1"
    db_port: int = 5432
    db_name: str = "projects"
    db_user: str = "javier"
    db_password: str

    app_host: str = "0.0.0.0"
    app_port: int = 8000


settings = Settings()
