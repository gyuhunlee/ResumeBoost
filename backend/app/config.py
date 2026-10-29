from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    cors_origins: str = "http://localhost:5173"
    supabase_url: str
    # Server-only key (Supabase → Project Settings → API keys → secret / service_role).
    # Bypasses RLS, so it must never reach the frontend.
    supabase_service_key: str = ""

    # Public URLs, used to build the Gmail OAuth redirect and send the user back.
    api_public_url: str = "http://localhost:8000"
    frontend_url: str = "http://localhost:5173"

    # Google Cloud OAuth client (can be the same one Supabase uses for login).
    google_client_id: str = ""
    google_client_secret: str = ""

    # Fernet key that encrypts Gmail refresh tokens at rest. Generate with:
    #   python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
    token_encryption_key: str = ""

    # Shared secret for the daily GitHub Actions job that calls /internal/sync-all.
    cron_secret: str = ""

    # Optional. Without a key the email classifier falls back to keyword rules.
    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.5-flash"

    @property
    def gmail_redirect_uri(self) -> str:
        return f"{self.api_public_url.rstrip('/')}/api/gmail/callback"


settings = Settings()
