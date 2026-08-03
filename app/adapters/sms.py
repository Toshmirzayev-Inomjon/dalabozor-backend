"""SMS adapter: interfeys + Mock (dev). Prod uchun Eskiz slot bo'sh qoldirilgan."""
import logging
from abc import ABC, abstractmethod

from app.core.config import settings

logger = logging.getLogger("dalabozor.sms")


class SmsAdapter(ABC):
    @abstractmethod
    async def send(self, phone: str, text: str) -> str:
        """SMS yuboradi, provayder holatini ('sent'/'failed') qaytaradi."""
        ...


class MockSmsAdapter(SmsAdapter):
    """Dev: hech qayerga yubormaydi, faqat log'ga yozadi."""

    async def send(self, phone: str, text: str) -> str:
        logger.info("📨 [MOCK SMS] %s → %s", phone, text)
        return "sent"


class EskizAdapter(SmsAdapter):
    """Prod slot — keyinchalik Eskiz.uz API bilan to'ldiriladi."""

    async def send(self, phone: str, text: str) -> str:  # pragma: no cover
        raise NotImplementedError("EskizAdapter hali ulanmagan — SMS_PROVIDER=mock ishlating")


def get_sms_adapter() -> SmsAdapter:
    if settings.sms_provider == "eskiz":
        return EskizAdapter()
    return MockSmsAdapter()
