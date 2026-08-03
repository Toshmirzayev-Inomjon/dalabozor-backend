"""Ilova konfiguratsiyasi — barcha sozlamalar `.env` dan o'qiladi."""

from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    # Ilova
    app_name: str = "DalaBozor API"
    env: str = "dev"
    api_v1_prefix: str = "/api/v1"
    debug: bool = True

    # Baza
    database_url: str = (
        "postgresql+asyncpg://dalabozor:dalabozor@localhost:5432/dalabozor"
    )

    # Railway kabi provayderlar DATABASE_URL'ni `postgresql://` ko'rinishida
    # beradi, lekin kod asyncpg talab qiladi — avtomatik moslashtiramiz.
    @field_validator("database_url")
    @classmethod
    def normalize_database_url(cls, value: str) -> str:
        if value.startswith("postgres://"):
            value = value.replace("postgres://", "postgresql+asyncpg://", 1)
        elif value.startswith("postgresql://"):
            value = value.replace("postgresql://", "postgresql+asyncpg://", 1)
        return value

    # JWT
    jwt_secret: str = "CHANGE_ME_super_secret_key_min_32_chars_long"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60
    refresh_token_expire_days: int = 30

    # Karta shifrlash
    card_encryption_key: str = ""

    # OTP
    otp_expire_seconds: int = 120
    otp_length: int = 4
    otp_dev_code: str = "1111"
    otp_max_attempts: int = 5
    # SMS-bombing himoyasi: bitta telefonga resend oralig'i va kunlik/soatlik cheklov
    otp_resend_cooldown_seconds: int = 60
    otp_max_per_hour: int = 5

    # Narx koridori
    corridor_percent: float = 10.0

    # SMS
    sms_provider: str = "mock"
    eskiz_email: str = ""
    eskiz_password: str = ""
    eskiz_from: str = "4546"

    # Telegram bot — ishonchli login (bot raqamni contact orqali oladi, SMS shart emas)
    bot_api_secret: str = "dev-bot-secret"
    # Web App (Mini App) initData'ni tekshirish uchun bot tokeni
    bot_token: str = ""

    # AI yordamchi — kalitlar faqat backend `.env` faylida saqlanadi
    groq_api_key: str = ""
    groq_base_url: str = "https://api.groq.com/openai/v1"
    groq_model: str = "llama-3.3-70b-versatile"
    ai_request_timeout_seconds: float = 30.0
    ai_chat_max_output_tokens: int = 900

    # To'lov
    payment_provider: str = "mock"
    payme_merchant_id: str = ""
    payme_key: str = ""
    click_merchant_id: str = ""
    click_service_id: str = ""
    click_secret: str = ""

    # Cron
    allocation_hour: int = 21
    payout_hour: int = 12
    scheduler_enabled: bool = True

    @property
    def is_prod(self) -> bool:
        return self.env == "prod"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
