"""SMS xizmati — adapter orqali yuboradi va sms_log ga yozadi."""
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.sms import get_sms_adapter
from app.models.user import SmsLog


class SmsService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.adapter = get_sms_adapter()

    async def send(self, phone: str, text: str) -> None:
        status = await self.adapter.send(phone, text)
        self.db.add(SmsLog(phone=phone, text=text, status=status))
        await self.db.flush()
