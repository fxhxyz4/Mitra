from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=("../.env", ".env"), extra="ignore", env_ignore_empty=True)

    app_name: str = "Mitra API"
    api_prefix: str = "/api"
    cors_origins: str = "http://localhost:5173,http://localhost:4173"

    ollama_url: str = "http://localhost:11434"
    ollama_model: str = "gemma3:4b"
    embed_model: str = "bge-m3"
    ollama_keep_alive: str = "30m"
    llm_temperature: float = 0
    llm_seed: int = 42
    llm_base_url: str = ""  # OpenAI-compatible, e.g. https://host/v1; empty = Ollama
    llm_model: str = ""
    llm_api_key: str = ""
    llm_timeout: float = 300  # seconds
    llm_cache_days: int = 7  # stored model answers are reused this long; 0 = no reuse
    llm_max_tokens: int = 2048  # caps a runaway generation; normal answers are a few hundred tokens
    ai_enabled: bool = True
    ai_max_upload_mb: int = 10  # MB
    ai_concurrency: int = 1  # model requests at a time; Ollama serves one anyway
    ai_wait_seconds: float = 2  # longer AI work answers 202 + job id

    database_url: str = f"sqlite:///{(BACKEND_DIR / 'data' / 'app.db').as_posix()}"
    storage_dir: Path = BACKEND_DIR / "data" / "evidence"
    demo_dataset: bool = True
    dataset_file: Path | None = None  # default: app/datasets/zavdannia-2/nabir.json
    seed_demo_data: bool = True
    reminder_days: str = "7,3,1"  # days before deadline
    demo_today: date | None = None  # YYYY-MM-DD; empty = real date
    timezone: str = "Europe/Kyiv"  # deadlines, "today" and the daily job run on this local time
    import_file: Path | None = None

    # python -c "from app.auth import hash_secret; print(hash_secret('…'))"; empty = granting ADMIN is off
    admin_grant_hash: str = ""
    # Demo accounts get tokens derived from this secret: python -c "import secrets;print(secrets.token_urlsafe(24))"
    demo_token_secret: str = ""
    demo_public_tokens: bool = False  # tests only: plain demo-coord, demo-ex-fin …
    demo_login: bool = False  # login page lists demo accounts (GET /auth/demo-accounts)

    session_hours: int = 12  # a sign-in token expires after this long without use
    session_max_days: int = 7  # and in any case this long after sign-in
    token_days: int = 90  # a personal token issued by an admin works this long; 0 = no expiry
    session_secret: str = ""  # required key for session tokens (only tests may leave it empty)
    session_cookie_secure: bool = True  # Secure flag on the session cookie; false only for plain-http deployments

    site_url: str = "http://localhost"
    report_secret: str = ""  # empty = random key next to storage_dir

    smtp_host: str = ""  # empty = in-app reminders only
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from: str = "noreply@example.org"
    smtp_starttls: bool = True
    notify_interval_minutes: int = 15  # minutes
    notify_max_age_days: int = 2  # days

    integra_url: str = ""  # e.g. http://integra/api/v1; empty = integration off
    integra_api_key: str = ""  # shared X-Integration-Key, both directions
    integra_timeout: float = 5.0  # seconds
    integra_interval_seconds: int = 30

    @field_validator("database_url")
    @classmethod
    def _sync_driver(cls, v: str) -> str:
        for prefix in ("postgresql+asyncpg://", "postgresql://", "postgres://"):
            if v.startswith(prefix):
                return "postgresql+psycopg://" + v[len(prefix):]
        return v

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def tz(self) -> ZoneInfo:
        return ZoneInfo(self.timezone)

    @property
    def reminder_day_list(self) -> list[int]:
        return [int(d) for d in self.reminder_days.split(",") if d.strip()]


settings = Settings()


def now() -> datetime:
    return datetime.now(settings.tz)


def today() -> date:
    return settings.demo_today or now().date()
