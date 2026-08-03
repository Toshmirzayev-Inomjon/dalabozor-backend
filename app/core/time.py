"""Biznes sanasi — Asia/Tashkent vaqt mintaqasi (scheduler va cron uchun).

Server OS vaqti UTC bo'lsa ham kunlik sikl (18:00/20:00/21:00/12:00)
kalendar kuni Toshkent vaqti bilan hisoblanadi.
"""

from datetime import date as date_type
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

BUSINESS_TZ = ZoneInfo("Asia/Tashkent")


def today() -> date_type:
    return datetime.now(BUSINESS_TZ).date()


def tomorrow() -> date_type:
    return today() + timedelta(days=1)
