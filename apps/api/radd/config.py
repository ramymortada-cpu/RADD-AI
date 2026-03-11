from pydantic_settings import BaseSettings, SettingsConfigDict


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

    # Confidence thresholds
    confidence_auto_threshold: float = 0.85
    confidence_soft_escalation_threshold: float = 0.60


settings = Settings()
