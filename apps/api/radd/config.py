from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Weak keys that must never be used in production (token encryption, etc.)
_WEAK_SECRET_KEYS = frozenset({"change-me", "radd-default-secret", ""})
_MIN_SECRET_KEY_LEN = 32


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Application
    app_env: str = "development"
    app_version: str = "0.1.0"
    secret_key: str = "change-me"
    debug: bool = True

    # CORS — dev origins always include localhost:3000 (Next.js dev server)
    cors_origins: list[str] = [
        "http://localhost:3000",
        "http://localhost:3001",
        "http://127.0.0.1:3000",
    ]

    # Database
    database_url: str = "postgresql+asyncpg://radd:radd_dev_password@localhost:5432/radd_dev"

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # Qdrant
    qdrant_url: str = "http://localhost:6333"
    qdrant_api_key: str = ""

    # S3 / MinIO
    s3_endpoint_url: str = "http://localhost:9000"
    s3_access_key: str = "radd_minio"
    s3_secret_key: str = "radd_minio_password"
    s3_bucket_name: str = "radd-dev"

    # JWT
    jwt_secret_key: str = "change-me-jwt"
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 15
    jwt_refresh_token_expire_days: int = 7

    # Sentry
    sentry_dsn: str | None = None

    # Rate Limiting
    default_rate_limit: str = "100/minute"
    auth_rate_limit: str = "10/minute"

    # WhatsApp Cloud API
    meta_app_secret: str = ""
    meta_verify_token: str = "radd_webhook_verify"
    wa_phone_number_id: str = ""
    wa_business_account_id: str = ""
    wa_api_token: str = ""
    wa_api_version: str = "v21.0"

    @property
    def wa_api_base_url(self) -> str:
        return f"https://graph.facebook.com/{self.wa_api_version}"

    # OpenAI
    openai_api_key: str = ""
    openai_embedding_model: str = "text-embedding-3-small"
    openai_chat_model: str = "gpt-4.1-mini"

    # Salla
    salla_client_id: str = ""
    salla_client_secret: str = ""

    # Zid Webhook
    zid_webhook_secret: str = Field(
        default="",
        description="Zid webhook secret for HMAC-SHA256 verification",
    )

    # Alerting
    slack_alert_webhook_url: str = Field(
        default="",
        description="Slack Incoming Webhook URL for CRITICAL/FATAL alerts",
    )

    # Confidence thresholds
    confidence_auto_threshold: float = 0.85
    confidence_soft_escalation_threshold: float = 0.60

    # Shadow Mode — process messages fully but do NOT send WhatsApp responses.
    # Set to true for 48-hour pre-pilot dry run. Responses are logged only.
    shadow_mode: bool = False

    # Pipeline v2 — Intent (LLM) and Verifier (NLI). Set True to enable.
    use_intent_v2: bool = False
    use_verifier_v2: bool = False

    @model_validator(mode="after")
    def validate_production_secret_key(self) -> "Settings":
        """In production, SECRET_KEY must be strong (≥32 chars, not a known weak value)."""
        if self.app_env != "production":
            return self
        sk = (self.secret_key or "").strip()
        if sk in _WEAK_SECRET_KEYS:
            raise ValueError(
                "SECRET_KEY must be set to a strong value in production. "
                "Generate one with: python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\""
            )
        if len(sk) < _MIN_SECRET_KEY_LEN:
            raise ValueError(
                f"SECRET_KEY must be at least {_MIN_SECRET_KEY_LEN} characters in production. "
                f"Current length: {len(sk)}"
            )
        return self


settings = Settings()
