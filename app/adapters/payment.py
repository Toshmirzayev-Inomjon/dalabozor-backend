"""To'lov adapteri (Billing Hub uslubi): interfeys + Mock. Payme/Click prod slot.

Karta to'liq raqami/CVV/expiry HECH QACHON bu yerga kelmaydi — faqat token.
"""
import logging
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass

from app.core.config import settings

logger = logging.getLogger("dalabozor.payment")


@dataclass
class PaymentResult:
    success: bool
    provider_ref: str | None = None
    error: str | None = None


@dataclass
class TokenizationResult:
    """Provayder tokenizatsiya oynasi/URL va (mock'da) tayyor token."""
    redirect_url: str
    token: str | None = None
    last4: str | None = None
    brand: str | None = None


class PaymentAdapter(ABC):
    @abstractmethod
    async def start_tokenization(self, user_id: str) -> TokenizationResult:
        """Karta bog'lash oynasini boshlaydi."""
        ...

    @abstractmethod
    async def charge(self, token: str, amount: int) -> PaymentResult:
        """Token orqali pul yechadi (invoice)."""
        ...

    @abstractmethod
    async def payout(self, token: str, amount: int) -> PaymentResult:
        """Kartaga pul o'tkazadi (dehqon payout)."""
        ...


class MockPaymentAdapter(PaymentAdapter):
    """Dev: hech qanday real pul harakati yo'q, doim muvaffaqiyat."""

    async def start_tokenization(self, user_id: str) -> TokenizationResult:
        fake_token = f"mock_tok_{uuid.uuid4().hex[:16]}"
        logger.info("💳 [MOCK] tokenization user=%s → %s", user_id, fake_token)
        return TokenizationResult(
            redirect_url=f"https://mock.pay/checkout/{user_id}",
            token=fake_token,
            last4="4242",
            brand="mock",
        )

    async def charge(self, token: str, amount: int) -> PaymentResult:
        logger.info("💳 [MOCK] charge %s so'm (token=%s)", amount, token[:12])
        return PaymentResult(success=True, provider_ref=f"mock_ch_{uuid.uuid4().hex[:12]}")

    async def payout(self, token: str, amount: int) -> PaymentResult:
        logger.info("💸 [MOCK] payout %s so'm (token=%s)", amount, token[:12] if token else "-")
        return PaymentResult(success=True, provider_ref=f"mock_po_{uuid.uuid4().hex[:12]}")


class PaymeAdapter(PaymentAdapter):  # pragma: no cover
    """Prod slot — Payme integratsiyasi keyin ulanadi."""

    async def start_tokenization(self, user_id: str) -> TokenizationResult:
        raise NotImplementedError("PaymeAdapter hali ulanmagan")

    async def charge(self, token: str, amount: int) -> PaymentResult:
        raise NotImplementedError

    async def payout(self, token: str, amount: int) -> PaymentResult:
        raise NotImplementedError


class ClickAdapter(PaymentAdapter):  # pragma: no cover
    """Prod slot — Click integratsiyasi keyin ulanadi."""

    async def start_tokenization(self, user_id: str) -> TokenizationResult:
        raise NotImplementedError("ClickAdapter hali ulanmagan")

    async def charge(self, token: str, amount: int) -> PaymentResult:
        raise NotImplementedError

    async def payout(self, token: str, amount: int) -> PaymentResult:
        raise NotImplementedError


def get_payment_adapter() -> PaymentAdapter:
    if settings.payment_provider == "payme":
        return PaymeAdapter()
    if settings.payment_provider == "click":
        return ClickAdapter()
    return MockPaymentAdapter()
