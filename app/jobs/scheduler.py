"""APScheduler — cron joblar (21:00 allocation, 12:00 payout).

Faza 4 da joblar to'liq ulanadi. Hozircha scheduler karkas sifatida turadi.
"""

import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from app.core.config import settings

logger = logging.getLogger("dalabozor.scheduler")

scheduler = AsyncIOScheduler(timezone="Asia/Tashkent")


async def _allocation_job() -> None:
    """21:00 — buyurtmalarni takliflarga taqsimlash."""
    from app.core.db import SessionLocal
    from app.core.time import tomorrow
    from app.services.allocation import AllocationService

    target = tomorrow()  # ertangi yig'im (Toshkent vaqti bo'yicha)
    async with SessionLocal() as db:
        await AllocationService(db).run(target)
        await db.commit()
    logger.info("✅ Allocation job bajarildi: %s", target)


async def _payout_job() -> None:
    """12:00 — bugungi qabullar bo'yicha payout."""
    from app.core.db import SessionLocal
    from app.core.time import today
    from app.services.payout import PayoutService

    async with SessionLocal() as db:
        await PayoutService(db).run(today())
        await db.commit()
    logger.info("✅ Payout job bajarildi")


def start_scheduler() -> None:
    if scheduler.running:
        return
    scheduler.add_job(
        _allocation_job,
        CronTrigger(hour=settings.allocation_hour, minute=0),
        id="allocation",
        replace_existing=True,
    )
    scheduler.add_job(
        _payout_job,
        CronTrigger(hour=settings.payout_hour, minute=0),
        id="payout",
        replace_existing=True,
    )
    scheduler.start()
    logger.info(
        "🕒 Scheduler ishga tushdi (allocation %02d:00, payout %02d:00)",
        settings.allocation_hour,
        settings.payout_hour,
    )


def shutdown_scheduler() -> None:
    if scheduler.running:
        scheduler.shutdown(wait=False)
