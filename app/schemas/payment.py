"""To'lov sxemalari."""
from pydantic import BaseModel, Field

from app.models.enums import CardProvider, PaymentStatus


class CardLinkIn(BaseModel):
    provider: CardProvider = CardProvider.payme


class CardLinkOut(BaseModel):
    redirect_url: str
    last4: str | None = None
    brand: str | None = None


class InvoiceIn(BaseModel):
    order_id: str


class PayoutIn(BaseModel):
    farmer_id: str
    amount: int = Field(..., gt=0)


class PaymentOut(BaseModel):
    id: str
    type: str
    amount: int
    method: str
    status: PaymentStatus
    provider_ref: str | None = None
