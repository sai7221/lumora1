"""
Loads all secrets/config from environment variables.
NEVER hardcode secrets here — they come from .env (local) or the
hosting platform's environment variable settings (Render, in production).
"""
import os
from dotenv import load_dotenv

load_dotenv()  # reads .env file in local dev; no-op if file doesn't exist


def _require(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(
            f"Missing required environment variable: {name}. "
            f"Check your .env file (copy .env.example to .env and fill it in)."
        )
    return value


class Settings:
    # Supabase
    SUPABASE_URL: str = _require("SUPABASE_URL")               # e.g. https://xxxx.supabase.co
    SUPABASE_ANON_KEY: str = _require("SUPABASE_ANON_KEY")     # "publishable" key — used for Auth calls
    SUPABASE_SERVICE_KEY: str = _require("SUPABASE_SERVICE_KEY")  # "secret" key — used for all DB REST calls

    # Gemini
    GEMINI_API_KEY: str = _require("GEMINI_API_KEY")

    # Derived
    SUPABASE_REST_URL: str = f"{SUPABASE_URL}/rest/v1"
    SUPABASE_AUTH_URL: str = f"{SUPABASE_URL}/auth/v1"


settings = Settings()
