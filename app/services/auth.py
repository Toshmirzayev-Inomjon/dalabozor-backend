"""Auth xizmati: OTP yaratish/tekshirish, user va rol boshqaruvi."""

import secrets
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.ratelimit import limit
from app.core.security import hash_secret, verify_secret
from app.models.enums import Role, Source
from app.models.farmer import Farmer
from app.models.restaurant import Restaurant
from app.models.user import OtpCode, User, UserRole
from app.services.sms import SmsService


class RoleNotAssignedError(Exception):
    """Foydalanuvchida olib tashlanayotgan rol mavjud emas."""


class ProtectedRoleRemovalError(Exception):
    """Himoyalangan rolni self-service oqimida olib tashlab bo'lmaydi."""

    def __init__(self, *args):
        super().__init__(*args)


class MultipleRoleError(Exception):
    """Bitta akkauntga bir nechta rol biriktirib bo'lmaydi."""


class AuthService:
    def __init__(self, db: AsyncSession):
        self.db = db

    # --- OTP ---
    def _generate_code(self) -> str:
        # Hibni SMS provayder (Eskiz) ulanmagan bo'lsa, doimiy test kodi ishlatiladi
        # — frontend shu kodni ko'rsatadi, hech qayerga SMS yuborilmaydi.
        if settings.sms_provider != "eskiz" and settings.otp_dev_code:
            return settings.otp_dev_code
        upper = 10**settings.otp_length
        return str(secrets.randbelow(upper)).zfill(settings.otp_length)

    async def request_otp(self, phone: str) -> str:
        # SMS-bombing himoyasi: bitta telefon uchun soatlik chegara + resend tanaffusi.
        limit(
            f"otp:{phone}",
            max_calls=settings.otp_max_per_hour,
            window_seconds=3600,
            cooldown_seconds=settings.otp_resend_cooldown_seconds,
        )
        code = self._generate_code()
        otp = OtpCode(
            phone=phone,
            code=hash_secret(code),
            expires_at=datetime.now(timezone.utc)
            + timedelta(seconds=settings.otp_expire_seconds),
            used=False,
        )
        self.db.add(otp)
        await self.db.flush()
        await SmsService(self.db).send(phone, f"DalaBozor tasdiqlash kodi: {code}")
        return code

    async def verify_otp(self, phone: str, code: str) -> tuple[User, bool]:
        """Kodni tekshiradi, user yo'q bo'lsa yaratadi. (user, is_new) qaytaradi."""
        stmt = (
            select(OtpCode)
            .where(OtpCode.phone == phone, OtpCode.used.is_(False))
            .order_by(OtpCode.created_at.desc())
        )
        otp = (await self.db.execute(stmt)).scalars().first()
        now = datetime.now(timezone.utc)
        if otp is None or otp.expires_at < now:
            raise ValueError("Kod noto'g'ri yoki muddati o'tgan")

        # Brute-force himoyasi: har bir urinish hisoblanadi, 5 dan oshsa kod
        # bekor qilinadi (foydalanuvchi yangi kod so'rashi kerak).
        otp.attempts += 1
        if otp.attempts >= settings.otp_max_attempts:
            otp.used = True
        await self.db.flush()
        if otp.used or not verify_secret(code, otp.code):
            raise ValueError("Kod noto'g'ri yoki muddati o'tgan")

        otp.used = True

        user = (
            await self.db.execute(select(User).where(User.phone == phone))
        ).scalar_one_or_none()
        is_new = user is None
        if is_new:
            user = User(phone=phone)
            self.db.add(user)
            await self.db.flush()
        return user, is_new

    async def telegram_login(
        self, phone: str, full_name: str | None, telegram_id: int | None = None
    ) -> tuple[User, bool]:
        """Bot ishonchli login: raqam bo'yicha user topadi yoki yaratadi (SMS'siz).

        `telegram_id` saqlanadi — keyin Web App (Mini App) shu orqali kiradi.
        """
        user = (
            await self.db.execute(select(User).where(User.phone == phone))
        ).scalar_one_or_none()
        is_new = user is None
        if is_new:
            user = User(phone=phone, full_name=full_name, telegram_id=telegram_id)
            self.db.add(user)
            await self.db.flush()
        else:
            if full_name and not user.full_name:
                user.full_name = full_name
            if telegram_id and user.telegram_id != telegram_id:
                user.telegram_id = telegram_id
            await self.db.flush()
        # `roles` munosabatini ochiq yuklaymiz (aks holda role_names lazy-load'da
        # async kontekst tashqarisida MissingGreenlet xatosi beradi).
        await self.db.refresh(user, attribute_names=["roles"])
        return user, is_new

    async def get_by_telegram_id(self, telegram_id: int) -> User | None:
        """Web App uchun: telegram_id bo'yicha userni topadi (rollari bilan)."""
        user = (
            await self.db.execute(select(User).where(User.telegram_id == telegram_id))
        ).scalar_one_or_none()
        if user is not None:
            await self.db.refresh(user, attribute_names=["roles"])
        return user

    # --- Rollar ---
    async def add_role(self, user: User, role: Role) -> None:
        # Bir userga parallel kelgan bir xil add-role so'rovlari unique constraint
        # bilan urishmasligi va domen profilini ikki marta yaratmasligi uchun
        # butun oqimni user qatori darajasida ketma-ketlashtiramiz.
        await self.db.execute(
            select(User.id).where(User.id == user.id).with_for_update()
        )
        owned = (
            (
                await self.db.execute(
                    select(UserRole.role)
                    .where(UserRole.user_id == user.id)
                    .with_for_update()
                )
            )
            .scalars()
            .all()
        )

        # Bitta akkaunt — bitta rol. Rol allaqachon biriktirilgan bo'lsa no-op;
        # boshqa rol biriktirish urinishi esa rad etiladi.
        if owned and role not in owned:
            raise MultipleRoleError("Bitta akkauntda faqat bitta rol bo'lishi mumkin")
        if role not in owned:
            self.db.add(UserRole(user_id=user.id, role=role))
            await self.db.flush()

        # Dehqon roli uchun profil qatorini ta'minlaymiz (offers FK uchun kerak).
        # Restoran profili nomi bilan alohida endpointda yaratiladi (Faza 3).
        if role == Role.farmer:
            farmer = await self.db.get(Farmer, user.id)
            if farmer is None:
                self.db.add(Farmer(user_id=user.id, source=Source.app))
                await self.db.flush()
        elif role == Role.restaurant:
            rest = await self.db.get(Restaurant, user.id)
            if rest is None:
                self.db.add(
                    Restaurant(user_id=user.id, name=user.full_name or "Restoran")
                )
                await self.db.flush()

    async def remove_role(self, user: User, role: Role) -> None:
        """Rol mappingini olib tashlaydi, domen profilini saqlaydi."""
        if role == Role.admin:
            raise ProtectedRoleRemovalError

        # Bitta foydalanuvchining parallel remove so'rovlari uni tasodifan
        # rolsiz qoldirmasligi uchun barcha rol qatorlarini qulflaymiz.
        roles = (
            (
                await self.db.execute(
                    select(UserRole)
                    .where(UserRole.user_id == user.id)
                    .order_by(UserRole.id)
                    .with_for_update()
                )
            )
            .scalars()
            .all()
        )

        role_mapping = next((item for item in roles if item.role == role), None)
        if role_mapping is None:
            raise RoleNotAssignedError

        # Bitta akkaunt — bitta rol qoidasi tufayli domen profillari saqlanadi,
        # faqat ruxsatni ifodalovchi user_roles qatori o'chiriladi. Aks holda
        # foydalanuvchi rolsiz qoladi va o'zi qayta rol tanlashi mumkin
        # (yoki administrator qayta biriktiradi).
        await self.db.delete(role_mapping)
        await self.db.flush()
