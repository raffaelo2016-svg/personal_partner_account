import json

from pydantic_settings import BaseSettings

_INSECURE_DEFAULTS = {
    "SECRET_KEY": "change-me-to-random-64-char-string",
    "DB_PASSWORD": "secret",
    "S3_ACCESS_KEY": "minioadmin",
    "S3_SECRET_KEY": "minioadmin",
}


class Settings(BaseSettings):
    DATABASE_URL: str = "postgresql+asyncpg://app:secret@localhost:5432/partner_cabinet"
    DB_PASSWORD: str = "secret"

    REDIS_URL: str = "redis://localhost:6379/0"

    SECRET_KEY: str = "change-me-to-random-64-char-string"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    S3_ENDPOINT: str = "http://localhost:9000"
    # Публичный base-URL для presigned-ссылок (чтобы в ответе SPA не было
    # internal docker-хоста типа minio:9000). Пусто = fallback на S3_ENDPOINT.
    S3_PUBLIC_ENDPOINT: str = ""
    S3_ACCESS_KEY: str = "minioadmin"
    S3_SECRET_KEY: str = "minioadmin"
    S3_BUCKET: str = "partner-cabinet"

    CORS_ORIGINS: str = '["http://localhost:5173"]'

    ALLOWED_HOSTS: str = '["localhost","127.0.0.1"]'

    COOKIE_SECURE: bool = False
    COOKIE_SAMESITE: str = "lax"
    COOKIE_DOMAIN: str | None = None

    LOG_LEVEL: str = "INFO"

    OPENAI_API_KEY: str = ""

    YOOKASSA_SHOP_ID: str = ""
    YOOKASSA_SECRET_KEY: str = ""
    YOOKASSA_RETURN_URL: str = "http://localhost:5173/dashboard/finance/court-fees"

    YANDEX_CAPTCHA_SECRET_KEY: str = ""

    # Password recovery email. SMTP_PASSWORD must only be provided through
    # the environment; an empty host keeps delivery disabled in local dev.
    PUBLIC_APP_URL: str = "http://localhost:5173"
    SMTP_HOST: str = ""
    SMTP_PORT: int = 465
    SMTP_USERNAME: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM_EMAIL: str = ""
    SMTP_USE_SSL: bool = True
    SMTP_USE_STARTTLS: bool = False
    PASSWORD_RESET_EXPIRE_MINUTES: int = 30

    # Telegram bot for opt-in delivery of cabinet news and notifications.
    # Keep the token and webhook secret server-side only.
    TELEGRAM_BOT_TOKEN: str = ""
    TELEGRAM_BOT_USERNAME: str = ""
    TELEGRAM_WEBHOOK_SECRET: str = ""
    TELEGRAM_CONNECT_EXPIRE_MINUTES: int = 15

    # Bitrix24 OAuth integration. Tokens are stored encrypted in PostgreSQL;
    # the local application's credentials stay only in the server environment.
    BITRIX_CLIENT_ENDPOINT: str = ""
    BITRIX_ACCESS_TOKEN: str = ""
    BITRIX_CLIENT_ID: str = ""
    BITRIX_CLIENT_SECRET: str = ""
    BITRIX_SMART_PROCESS_ENTITY_TYPE_ID: int = 1070
    # Clients already in court go to the Arbitration deal pipeline.
    BITRIX_DEAL_CATEGORY_ID: int = 3
    # Clients transferred before filing go to the Support department pipeline,
    # straight into its first stage «Партнеры» (verified through the portal API),
    # not into the «Новый клиент» stage.
    BITRIX_SUPPORT_DEAL_CATEGORY_ID: int = 7
    BITRIX_SUPPORT_DEAL_STAGE_ID: str = "C7:UC_X16U4C"
    BITRIX_ALLOWED_DOMAIN: str = "bitrix.uriteh.ru"
    BITRIX_TOKEN_ENCRYPTION_KEY: str = ""
    BITRIX_OUTBOX_BATCH_SIZE: int = 25
    BITRIX_OUTBOX_MAX_ATTEMPTS: int = 8
    BITRIX_RETRY_BASE_SECONDS: int = 30
    BITRIX_RETRY_MAX_SECONDS: int = 3600
    BITRIX_PROCESSING_STALE_MINUTES: int = 15
    BITRIX_RECONCILE_AFTER_HOURS: int = 24
    # Employees added to the internal Bitrix chat created for each partner.
    # Accepts either a JSON array ("[55,57]") or a comma/space separated list.
    BITRIX_CHAT_SUPPORT_USER_IDS: str = ""
    # Required chat participants. They are resolved to active Bitrix24 users at runtime,
    # so the setting does not depend on environment-specific Bitrix user IDs.
    BITRIX_CHAT_SUPPORT_USER_NAMES: str = (
        '["Протацкая Тамара","Швецова Тамара","Агейчик Нина","Самсонюк Евгений"]'
    )
    BITRIX_CHAT_PROVISION_BATCH_SIZE: int = 25
    BITRIX_CHAT_EXCLUDED_PARTNER_TERMS: str = (
        '["агейчик","протацкая","ифнс","федеральная налоговая служба","косточкина"]'
    )

    ENVIRONMENT: str = "development"

    @property
    def cors_origins_list(self) -> list[str]:
        try:
            value = json.loads(self.CORS_ORIGINS)
        except json.JSONDecodeError as err:
            raise RuntimeError(f"CORS_ORIGINS is not valid JSON: {err}") from err
        if not isinstance(value, list) or not all(isinstance(v, str) for v in value):
            raise RuntimeError("CORS_ORIGINS must be a JSON list of strings")
        if self.ENVIRONMENT in ("production", "staging") and "*" in value:
            raise RuntimeError("CORS wildcard '*' is not allowed in production/staging")
        return value

    @property
    def allowed_hosts_list(self) -> list[str]:
        try:
            value = json.loads(self.ALLOWED_HOSTS)
        except json.JSONDecodeError as err:
            raise RuntimeError(f"ALLOWED_HOSTS is not valid JSON: {err}") from err
        if not isinstance(value, list) or not all(isinstance(v, str) for v in value):
            raise RuntimeError("ALLOWED_HOSTS must be a JSON list of strings")
        if self.ENVIRONMENT in ("production", "staging") and "*" in value:
            raise RuntimeError("ALLOWED_HOSTS wildcard '*' is not allowed in production/staging")
        return value

    @property
    def bitrix_chat_support_user_ids(self) -> list[int]:
        raw = self.BITRIX_CHAT_SUPPORT_USER_IDS.strip()
        if not raw:
            return []
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            parsed = raw.replace(",", " ").split()
        if not isinstance(parsed, list):
            raise RuntimeError("BITRIX_CHAT_SUPPORT_USER_IDS must be a JSON list or a comma-separated list")
        result: list[int] = []
        for item in parsed:
            text = str(item).strip()
            if not text.isdigit() or int(text) <= 0:
                raise RuntimeError("BITRIX_CHAT_SUPPORT_USER_IDS contains an invalid user ID")
            value = int(text)
            if value not in result:
                result.append(value)
        return result

    @property
    def bitrix_chat_support_user_names(self) -> tuple[str, ...]:
        try:
            parsed = json.loads(self.BITRIX_CHAT_SUPPORT_USER_NAMES)
        except json.JSONDecodeError as err:
            raise RuntimeError(f"BITRIX_CHAT_SUPPORT_USER_NAMES is not valid JSON: {err}") from err
        if not isinstance(parsed, list) or not all(isinstance(item, str) and item.strip() for item in parsed):
            raise RuntimeError("BITRIX_CHAT_SUPPORT_USER_NAMES must be a JSON list of non-empty strings")
        return tuple(item.strip() for item in parsed)

    @property
    def bitrix_chat_excluded_partner_terms(self) -> tuple[str, ...]:
        try:
            parsed = json.loads(self.BITRIX_CHAT_EXCLUDED_PARTNER_TERMS)
        except json.JSONDecodeError as err:
            raise RuntimeError(f"BITRIX_CHAT_EXCLUDED_PARTNER_TERMS is not valid JSON: {err}") from err
        if not isinstance(parsed, list) or not all(isinstance(item, str) and item.strip() for item in parsed):
            raise RuntimeError("BITRIX_CHAT_EXCLUDED_PARTNER_TERMS must be a JSON list of non-empty strings")
        return tuple(item.strip().casefold() for item in parsed)

    @property
    def sync_database_url(self) -> str:
        """URL with psycopg2 driver for Alembic migrations."""
        return self.DATABASE_URL.replace("+asyncpg", "+psycopg2")

    def validate_production_secrets(self) -> None:
        if self.ENVIRONMENT not in ("production", "staging"):
            return
        for field, insecure_value in _INSECURE_DEFAULTS.items():
            if getattr(self, field) == insecure_value:
                raise RuntimeError(
                    f"Insecure default for {field} in {self.ENVIRONMENT}. "
                    f"Set {field} via environment variable or .env file."
                )
        if not self.COOKIE_SECURE:
            raise RuntimeError(f"COOKIE_SECURE must be true in {self.ENVIRONMENT} (HTTPS-only cookies).")

    model_config = {"env_file": ".env", "extra": "ignore"}


settings = Settings()
settings.validate_production_secrets()
# Fail fast on bad CORS_ORIGINS / ALLOWED_HOSTS — parse once at boot.
_ = settings.cors_origins_list
_ = settings.allowed_hosts_list
