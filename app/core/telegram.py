"""Telegram Web App (Mini App) initData tekshiruvi.

Telegram initData'ni bot tokeni bilan imzolaydi. Biz HMAC-SHA256 orqali
haqiqiyligini tekshiramiz (rasmiy algoritm).
Hujjat: https://core.telegram.org/bots/webapps#validating-data-received-via-the-mini-app
"""

import hashlib
import hmac
import json
from datetime import datetime, timezone
from urllib.parse import parse_qsl

# Eski (takror uzatilgan) initData'ni qabul qilmaymiz. Telegram buni talab
# qiladi: imzo faqat haqiqiylikni isbotlaydi, "hozir"ligini emas.
MAX_INIT_DATA_AGE_SECONDS = 24 * 60 * 60


def validate_init_data(init_data: str, bot_token: str) -> dict | None:
    """initData to'g'ri imzolangan bo'lsa, ajratilgan maydonlarni qaytaradi.

    Telegram user ma'lumotini tekshiradi:
      - hash imzosi to'g'ri bo'lishi kerak,
      - `auth_date` eskirgan bo'lmasligi kerak (replay hujumi).
    Noto'g'ri bo'lsa None.
    """
    if not init_data or not bot_token:
        return None
    try:
        pairs = dict(parse_qsl(init_data, keep_blank_values=True))
    except Exception:
        return None

    received_hash = pairs.pop("hash", None)
    if not received_hash:
        return None

    # auth_date imzoga KIradi — shuning uchun data_check_string'ni qurishda
    # pairs ichida qolishi kerak. Faqat eskirganlikni tekshirish uchun o'qiymiz.
    auth_date_raw = pairs.get("auth_date")
    if auth_date_raw is None:
        return None

    data_check_string = "\n".join(f"{k}={pairs[k]}" for k in sorted(pairs.keys()))
    secret_key = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
    calc_hash = hmac.new(
        secret_key, data_check_string.encode(), hashlib.sha256
    ).hexdigest()

    if not hmac.compare_digest(calc_hash, received_hash):
        return None

    # Eskirgan (takror uzatilgan) initData'ni qabul qilmaymiz (replay hujumi).
    try:
        auth_date = int(auth_date_raw)
    except (TypeError, ValueError):
        return None
    age_seconds = datetime.now(timezone.utc).timestamp() - auth_date
    if age_seconds < 0 or age_seconds > MAX_INIT_DATA_AGE_SECONDS:
        return None

    # user maydonini ochamiz
    result: dict[str, object] = dict(pairs)
    if "user" in result:
        user_raw = result["user"]
        if isinstance(user_raw, str):
            try:
                result["user"] = json.loads(user_raw)
            except Exception:
                result["user"] = None
        else:
            result["user"] = None
    return result
