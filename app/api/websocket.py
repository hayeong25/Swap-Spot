import asyncio
import json
import logging
from datetime import datetime

import pytz
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.services.rate_service import rate_cache
from app.utils.currency import MAJOR_CURRENCIES

logger = logging.getLogger(__name__)
router = APIRouter()
KST = pytz.timezone("Asia/Seoul")

connected_clients: set[WebSocket] = set()


@router.websocket("/ws/rates")
async def websocket_rates(ws: WebSocket):
    await ws.accept()
    connected_clients.add(ws)
    logger.info(f"WS client connected (total: {len(connected_clients)})")

    try:
        # 연결 즉시 현재 캐시 데이터 전송
        rates = rate_cache.get_all()
        if rates:
            snapshot = {
                code: {
                    "currency_code": r.currency_code,
                    "rate": r.rate,
                    "cash_buy_rate": r.cash_buy_rate,
                    "cash_sell_rate": r.cash_sell_rate,
                    "source": r.source,
                    "updated_at": r.fetched_at.isoformat(),
                }
                for code, r in rates.items()
                if code in MAJOR_CURRENCIES
            }
            await ws.send_text(json.dumps({"type": "snapshot", "data": snapshot}, ensure_ascii=False))

        # 클라이언트 연결 유지 (ping/pong)
        while True:
            await asyncio.wait_for(ws.receive_text(), timeout=60)
    except (WebSocketDisconnect, asyncio.TimeoutError):
        pass
    finally:
        connected_clients.discard(ws)
        logger.info(f"WS client disconnected (total: {len(connected_clients)})")


async def broadcast_rates(rates: dict):
    if not connected_clients:
        return

    payload = json.dumps({
        "type": "update",
        "data": {
            code: {
                "currency_code": r.currency_code,
                "rate": r.rate,
                "cash_buy_rate": r.cash_buy_rate,
                "cash_sell_rate": r.cash_sell_rate,
                "source": r.source,
                "updated_at": r.fetched_at.isoformat(),
            }
            for code, r in rates.items()
            if code in MAJOR_CURRENCIES
        },
        "timestamp": datetime.now(KST).isoformat(),
    }, ensure_ascii=False)

    disconnected = set()
    for ws in connected_clients:
        try:
            await ws.send_text(payload)
        except Exception:
            disconnected.add(ws)

    connected_clients.difference_update(disconnected)
