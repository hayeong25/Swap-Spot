import logging
from datetime import datetime, timedelta

import httpx
import pytz
from sqlalchemy import select

from app.config import settings
from app.models.alert import Alert
from app.models.database import async_session
from app.services.rate_service import get_rate_values, rate_cache

logger = logging.getLogger(__name__)
KST = pytz.timezone("Asia/Seoul")

ALERT_COOLDOWN_MINUTES = 60

alert_callbacks: list = []


def register_alert_callback(callback):
    alert_callbacks.append(callback)


async def evaluate_alerts():
    async with async_session() as session:
        stmt = select(Alert).where(Alert.is_active == True)
        result = await session.execute(stmt)
        alerts = result.scalars().all()

        for alert in alerts:
            cached = rate_cache.latest.get(alert.currency_code)
            if not cached:
                continue

            # 쿨다운 체크 — 마지막 발송 후 일정 시간 이내면 스킵
            if alert.last_triggered_at:
                cooldown_until = alert.last_triggered_at + timedelta(minutes=ALERT_COOLDOWN_MINUTES)
                if datetime.now(KST) < cooldown_until.replace(tzinfo=KST) if cooldown_until.tzinfo is None else cooldown_until:
                    continue

            triggered = False
            message = ""

            if alert.condition == "below" and cached.rate <= alert.threshold:
                triggered = True
                message = f"{alert.currency_code}/KRW 환율이 {cached.rate:,.2f}원으로 목표가 {alert.threshold:,.2f}원 이하 도달!"

            elif alert.condition == "above" and cached.rate >= alert.threshold:
                triggered = True
                message = f"{alert.currency_code}/KRW 환율이 {cached.rate:,.2f}원으로 {alert.threshold:,.2f}원 이상 도달!"

            elif alert.condition == "percent_change":
                rates = await get_rate_values(alert.currency_code, days=2)
                if len(rates) >= 2:
                    change_pct = abs(rates[-1] - rates[-2]) / rates[-2] * 100
                    if change_pct >= alert.threshold:
                        triggered = True
                        message = f"{alert.currency_code}/KRW 환율 변동 {change_pct:.2f}% (임계값 {alert.threshold}%)"

            if triggered:
                alert.last_triggered_at = datetime.now(KST)
                await session.commit()
                await dispatch_alert(alert, message)


async def dispatch_alert(alert: Alert, message: str):
    logger.info(f"ALERT: {message}")

    for callback in alert_callbacks:
        try:
            await callback(alert.currency_code, message)
        except Exception as e:
            logger.error(f"Alert callback error: {e}")

    if settings.telegram_bot_token and settings.telegram_chat_id:
        await send_telegram(message)


async def send_telegram(message: str, max_retries: int = 3):
    url = f"https://api.telegram.org/bot{settings.telegram_bot_token}/sendMessage"
    for attempt in range(max_retries):
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.post(url, json={
                    "chat_id": settings.telegram_chat_id,
                    "text": f"💱 Swap Spot Alert\n{message}",
                })
                if resp.status_code == 200:
                    return
                logger.warning(f"Telegram send returned {resp.status_code} (attempt {attempt + 1})")
        except Exception as e:
            logger.error(f"Telegram send failed (attempt {attempt + 1}): {e}")
    logger.error("Telegram send failed after all retries")
