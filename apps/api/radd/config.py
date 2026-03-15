import json
import logging

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)

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
    api_base_url: str = "http://localhost:8000"  # Override in production for Twilio callbacks

    # AWS Secrets Manager (production only)
    aws_secret_name: str = "radd/production/api_secrets"
    aws_region: str = "me-south-1"
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
    sentry_environment: str = "development"

    # Slack Alerts (CRITICAL/FATAL) — use SLACK_ALERT_WEBHOOK or SLACK_ALERT_WEBHOOK_URL
    slack_alert_webhook: str = ""

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

    # Twilio Voice (COD Shield - Egypt)
    twilio_account_sid: str = ""
    twilio_auth_token: str = ""
    twilio_phone_number: str = ""  # الرقم اللي هيتصل منه (بصيغة +20XXXXXXXXX أو Twilio number)

    # Zid Webhook
    zid_webhook_secret: str = Field(
        default="",
        description="Zid webhook secret for HMAC-SHA256 verification",
    )

    # Alerting (slack_alert_webhook_url kept for backward compatibility)
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

    def _load_secrets_from_aws(self) -> None:
        """Load sensitive settings from AWS Secrets Manager in production."""
        try:
            import boto3

            secret_name = self.aws_secret_name
            region_name = self.aws_region

            session = boto3.session.Session()
            client = session.client(
                service_name="secretsmanager",
                region_name=region_name,
            )

            response = client.get_secret_value(SecretId=secret_name)
            secrets = json.loads(response["SecretString"])

            field_mapping = {
                "DATABASE_URL": "database_url",
                "REDIS_URL": "redis_url",
                "OPENAI_API_KEY": "openai_api_key",
                "SECRET_KEY": "secret_key",
                "JWT_SECRET_KEY": "jwt_secret_key",
                "WA_API_TOKEN": "wa_api_token",
                "META_APP_SECRET": "meta_app_secret",
                "SENTRY_DSN": "sentry_dsn",
                "SLACK_ALERT_WEBHOOK": "slack_alert_webhook",
                "SALLA_CLIENT_ID": "salla_client_id",
                "SALLA_CLIENT_SECRET": "salla_client_secret",
            }

            loaded_count = 0
            for aws_key, settings_field in field_mapping.items():
                if aws_key in secrets and hasattr(self, settings_field):
                    setattr(self, settings_field, secrets[aws_key])
                    loaded_count += 1

            logger.info(
                "Loaded %d secrets from AWS Secrets Manager (secret=%s, region=%s)",
                loaded_count,
                secret_name,
                region_name,
            )

        except ImportError:
            logger.error("boto3 not installed — cannot load secrets from AWS")
        except Exception as e:
            logger.error("Failed to load secrets from AWS Secrets Manager: %s", e)
            # Do NOT crash the app — fall back to .env values

    @model_validator(mode="after")
    def _load_aws_secrets_in_production(self) -> "Settings":
        """Load secrets from AWS when in production."""
        if self.app_env == "production" and self.aws_secret_name:
            self._load_secrets_from_aws()
        return self

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
