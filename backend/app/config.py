"""Application settings, read from backend/.env.

Real environment variables take precedence over the file, so tests, CI and
containers can override values without editing .env.
"""
import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

BACKEND_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BACKEND_DIR / ".env", override=False)

MIN_JWT_SECRET_LENGTH = 32


class ConfigError(RuntimeError):
    """Raised at import time so a misconfigured app refuses to start."""


@dataclass(frozen=True)
class Settings:
    database_url: str
    jwt_secret_key: str
    jwt_algorithm: str
    access_token_expire_minutes: int
    mock_eligibility_url: str
    eligibility_timeout_seconds: float
    cors_origins: tuple[str, ...]


def _get(name: str, default: str) -> str:
    return os.getenv(name, "").strip() or default


def _get_number(name: str, default: str, cast: type[int] | type[float]) -> int | float:
    raw = _get(name, default)
    try:
        return cast(raw)
    except ValueError:
        raise ConfigError(f"{name} must be a number, got {raw!r}.") from None


def _database_url() -> str:
    url = _get("DATABASE_URL", "postgresql+psycopg://postgres:postgres@localhost:5432/plate_scan")
    # A bare postgresql:// URL makes SQLAlchemy look for psycopg2; this project ships psycopg 3.
    for prefix in ("postgresql://", "postgres://"):
        if url.startswith(prefix):
            return "postgresql+psycopg://" + url.removeprefix(prefix)
    return url


def _require_jwt_secret() -> str:
    secret = os.getenv("JWT_SECRET_KEY", "").strip()
    if not secret:
        raise ConfigError(
            "JWT_SECRET_KEY is not set. Copy backend/.env.example to backend/.env and set it, e.g. "
            'python -c "import secrets; print(secrets.token_hex(32))"'
        )
    # A short HS256 key can be brute-forced offline from any issued token.
    if len(secret) < MIN_JWT_SECRET_LENGTH:
        raise ConfigError(f"JWT_SECRET_KEY must be at least {MIN_JWT_SECRET_LENGTH} characters long.")
    return secret


def load_settings() -> Settings:
    cors = _get("CORS_ORIGINS", "http://localhost:5173")
    return Settings(
        database_url=_database_url(),
        jwt_secret_key=_require_jwt_secret(),
        jwt_algorithm=_get("JWT_ALGORITHM", "HS256"),
        access_token_expire_minutes=_get_number("ACCESS_TOKEN_EXPIRE_MINUTES", "60", int),
        mock_eligibility_url=_get(
            "MOCK_ELIGIBILITY_URL", "http://localhost:8000/mock/partner-network/eligibility"
        ),
        eligibility_timeout_seconds=_get_number("ELIGIBILITY_TIMEOUT_SECONDS", "3", float),
        cors_origins=tuple(origin.strip() for origin in cors.split(",") if origin.strip()),
    )


settings = load_settings()
