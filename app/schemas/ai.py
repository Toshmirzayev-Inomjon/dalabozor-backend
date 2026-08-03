"""AI yordamchi uchun kirish-chiqish sxemalari."""

from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from app.models.enums import Role

MAX_CHAT_MESSAGE_CHARS = 4_000
MAX_CHAT_HISTORY_MESSAGES = 16
MAX_CHAT_CONTEXT_CHARS = 16_000

ChatRole = Literal["user", "assistant"]
# Bitta akkaunt — bitta rol: AI rol qo'shish, olib tashlash yoki almashtirish
# kabi amallarni taklif qilmaydi, faqat bo'limlar orasida navigatsiya qiladi.
ActionType = Literal["navigate"]
DashboardSection = Literal[
    "overview",
    "new-offer",
    "offers",
    "payments",
    "profile",
    "catalog",
    "orders",
    "history",
]


class ChatHistoryMessage(BaseModel):
    role: ChatRole
    content: str = Field(min_length=1, max_length=MAX_CHAT_MESSAGE_CHARS)


class ChatIn(BaseModel):
    message: str = Field(min_length=1, max_length=MAX_CHAT_MESSAGE_CHARS)
    history: list[ChatHistoryMessage] = Field(
        default_factory=list, max_length=MAX_CHAT_HISTORY_MESSAGES
    )
    active_role: Role | None = None
    active_section: DashboardSection | None = None

    @field_validator("message")
    @classmethod
    def message_must_not_be_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Xabar bo'sh bo'lmasligi kerak")
        return value

    @model_validator(mode="after")
    def context_must_fit_limit(self) -> "ChatIn":
        total = len(self.message) + sum(len(item.content) for item in self.history)
        if total > MAX_CHAT_CONTEXT_CHARS:
            raise ValueError(
                f"Suhbat konteksti {MAX_CHAT_CONTEXT_CHARS} belgidan oshmasligi kerak"
            )
        return self


class AIAction(BaseModel):
    type: ActionType
    value: str = Field(min_length=1, max_length=40, pattern=r"^[a-z][a-z0-9-]*$")
    # AI faqat taklif beradi. Har qanday amalni UI foydalanuvchiga tasdiqlatadi.
    requires_confirmation: Literal[True] = True


class ChatOut(BaseModel):
    reply: str = Field(min_length=1, max_length=6_000)
    action: AIAction | None = None


class AIStatusOut(BaseModel):
    chat_available: bool
