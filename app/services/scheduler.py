import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from app.services.alert_service import evaluate_alerts
from app.services.rate_service import fetch_and_store
from app.sources.aggregator import RateAggregator
from app.utils.business_hours import is_banking_hours

logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler(timezone="Asia/Seoul")
_aggregator: RateAggregator | None = None


def init_scheduler(aggregator: RateAggregator):
    global _aggregator
    _aggregator = aggregator

    # 수출입은행: 매일 11:05 KST
    scheduler.add_job(
        _fetch_rates,
        CronTrigger(hour=11, minute=5, timezone="Asia/Seoul"),
        id="koreaexim_daily",
        name="Korea Exim daily fetch",
    )

    # 하나은행: 2분 간격 (영업시간 내만 실행)
    scheduler.add_job(
        _fetch_intraday,
        IntervalTrigger(minutes=2),
        id="hanabank_intraday",
        name="HanaBank intraday fetch",
    )

    # ECOS: 매일 18:00 KST
    scheduler.add_job(
        _fetch_rates,
        CronTrigger(hour=18, minute=0, timezone="Asia/Seoul"),
        id="ecos_daily",
        name="ECOS daily fetch",
    )

    # 알림 평가: 5분 간격
    scheduler.add_job(
        evaluate_alerts,
        IntervalTrigger(minutes=5),
        id="alert_eval",
        name="Alert evaluation",
    )

    scheduler.start()
    logger.info("Scheduler started")


async def _fetch_rates():
    if _aggregator:
        await fetch_and_store(_aggregator)


async def _fetch_intraday():
    if not is_banking_hours():
        return
    if _aggregator:
        await fetch_and_store(_aggregator)


def shutdown_scheduler():
    scheduler.shutdown(wait=False)
    logger.info("Scheduler shutdown")
