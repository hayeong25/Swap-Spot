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
_hanabank_aggregator: RateAggregator | None = None
_koreaexim_aggregator: RateAggregator | None = None
_ecos_aggregator: RateAggregator | None = None


def init_scheduler(aggregator: RateAggregator):
    global _aggregator, _hanabank_aggregator, _koreaexim_aggregator, _ecos_aggregator
    _aggregator = aggregator

    # 소스별 전용 aggregator 분리
    from app.sources.hanabank import HanaBankSource
    from app.sources.koreaexim import KoreaEximSource
    from app.sources.ecos import EcosSource

    hana_sources = [s for s in aggregator.sources if isinstance(s, HanaBankSource)]
    koreaexim_sources = [s for s in aggregator.sources if isinstance(s, KoreaEximSource)]
    ecos_sources = [s for s in aggregator.sources if isinstance(s, EcosSource)]

    _hanabank_aggregator = RateAggregator(hana_sources) if hana_sources else None
    _koreaexim_aggregator = RateAggregator(koreaexim_sources) if koreaexim_sources else None
    _ecos_aggregator = RateAggregator(ecos_sources) if ecos_sources else None

    # 수출입은행: 매일 11:05 KST
    scheduler.add_job(
        _fetch_koreaexim,
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
        _fetch_ecos,
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


async def _fetch_koreaexim():
    try:
        if _koreaexim_aggregator:
            await fetch_and_store(_koreaexim_aggregator)
    except Exception as e:
        logger.error(f"KoreaExim scheduled fetch failed: {e}")


async def _fetch_ecos():
    try:
        if _ecos_aggregator:
            await fetch_and_store(_ecos_aggregator)
    except Exception as e:
        logger.error(f"ECOS scheduled fetch failed: {e}")


async def _fetch_intraday():
    if not is_banking_hours():
        return
    try:
        if _hanabank_aggregator:
            await fetch_and_store(_hanabank_aggregator)
    except Exception as e:
        logger.error(f"HanaBank intraday fetch failed: {e}")


def shutdown_scheduler():
    scheduler.shutdown(wait=False)
    logger.info("Scheduler shutdown")
