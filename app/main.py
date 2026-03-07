import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.api.routes_alerts import router as alerts_router
from app.api.routes_rates import router as rates_router
from app.api.websocket import router as ws_router
from app.models.exchange_rate import Base
from app.models.database import engine
from app.api.websocket import broadcast_rates
from app.services.rate_service import fetch_and_store, load_latest_from_db, rate_cache, set_broadcast_callback
from app.services.scheduler import init_scheduler, shutdown_scheduler
from app.sources.aggregator import RateAggregator
from app.sources.ecos import EcosSource
from app.sources.hanabank import HanaBankSource
from app.sources.koreaexim import KoreaEximSource
from app.config import settings as _settings

logging.basicConfig(
    level=logging.WARNING if _settings.env == "production" else logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)

aggregator = RateAggregator([
    KoreaEximSource(),
    HanaBankSource(),
    EcosSource(),
])


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logging.info("Database tables created")

    # WebSocket broadcast 콜백 등록
    set_broadcast_callback(broadcast_rates)

    # 초기 데이터 로드
    try:
        await fetch_and_store(aggregator)
    except Exception as e:
        logging.warning(f"Initial fetch failed (will retry via scheduler): {e}")

    # API 소스에서 데이터를 못 가져온 경우, DB에서 최신 데이터 로드 (데모 데이터 포함)
    if not rate_cache.latest:
        await load_latest_from_db()

    logging.info(f"Initial rates loaded: {len(rate_cache.latest)} currencies")

    # 스케줄러 시작
    init_scheduler(aggregator)

    app.state.aggregator = aggregator

    yield

    # Shutdown
    shutdown_scheduler()


app = FastAPI(
    title="Swap Spot",
    description="실시간 환율 모니터 + 환전 타이밍 추천",
    version="1.0.0",
    lifespan=lifespan,
)

app.include_router(rates_router)
app.include_router(alerts_router)
app.include_router(ws_router)
app.mount("/", StaticFiles(directory="static", html=True), name="static")
