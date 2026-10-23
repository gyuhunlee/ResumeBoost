from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    cors_origins: str = "http://localhost:5173"
    supabase_url: str


settings = Settings()