"""WebSocket endpoints for tick streaming backed by ClickHouse."""
from __future__ import annotations

import asyncio
from datetime import date, datetime, time
from zoneinfo import ZoneInfo
from typing import Any, Dict, Iterable, List, Optional

import httpx
from clickhouse_driver import Client
from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect, status

from app.core.config import settings
from app.utils.logger import logger

router = APIRouter()
_MARKET_TZ = ZoneInfo(settings.market_timezone)

_TICK_FIELDS = [
    "ts_code",
    "name",
    "trade",
    "price",
    "open",
    "high",
    "low",
    "pre_close",
    "bid",
    "ask",
    "volume",
    "amount",
    "b1_v",
    "b1_p",
    "b2_v",
    "b2_p",
    "b3_v",
    "b3_p",
    "b4_v",
    "b4_p",
    "b5_v",
    "b5_p",
    "a1_v",
    "a1_p",
    "a2_v",
    "a2_p",
    "a3_v",
    "a3_p",
    "a4_v",
    "a4_p",
    "a5_v",
    "a5_p",
    "date",
    "time",
    "source",
    "raw_json",
]

_TRADING_WINDOWS = [
    (time(9, 15), time(9, 25)),
    (time(9, 30), time(11, 30)),
    (time(13, 0), time(15, 0)),
]

_CLICKHOUSE_COLUMNS = ", ".join(_TICK_FIELDS)


def _get_clickhouse_client() -> Client:
    return Client(
        host=settings.clickhouse_host,
        port=settings.clickhouse_port,
        user=settings.clickhouse_user,
        password=settings.clickhouse_password,
        database=settings.clickhouse_database,
        settings={"strings_as_bytes": False},
    )


_ch_client = _get_clickhouse_client()


@router.websocket("/ticks")
async def websocket_ticks(
    websocket: WebSocket, stock_code: str | None = Query(None, alias="stockCode")
):
    """Stream tick data updates for a given stock."""
    await websocket.accept()

    if not stock_code:
        await websocket.close(
            code=status.WS_1008_POLICY_VIOLATION,
            reason="stockCode is required",
        )
        return

    logger.info(f"[WebSocket] Client connected for {stock_code}")

    trade_date = await _fetch_latest_trading_day()
    if not trade_date:
        logger.error("无法获取最新交易日，终止 WebSocket 会话")
        await websocket.send_json(
            {"status": "non_trading", "historyTicks": [], "latestTicks": []}
        )
        await websocket.close(code=status.WS_1011_INTERNAL_ERROR)
        return

    history_ticks = _query_ticks(stock_code, trade_date, None)
    last_time = history_ticks[-1]["time"] if history_ticks else None

    status_text = _determine_status(datetime.now(_MARKET_TZ))
    await websocket.send_json(
        {
            "status": status_text,
            "historyTicks": history_ticks,
            "latestTicks": [],
        }
    )

    try:
        while True:
            await asyncio.sleep(3)
            status_text = _determine_status(datetime.now(_MARKET_TZ))
            latest_ticks: List[Dict[str, Any]] = []
            if status_text == "trading":
                latest_ticks = _query_ticks(stock_code, trade_date, last_time)
                if latest_ticks:
                    last_time = latest_ticks[-1]["time"]
            await websocket.send_json(
                {
                    "status": status_text,
                    "historyTicks": [],
                    "latestTicks": latest_ticks,
                }
            )
    except WebSocketDisconnect:
        logger.info(f"[WebSocket] Client disconnected for {stock_code}")


def _determine_status(now: datetime) -> str:
    current_time = now.time()
    for start, end in _TRADING_WINDOWS:
        if start <= current_time <= end:
            return "trading"

    morning = time(9, 15)
    evening = time(15, 0)
    if evening <= current_time or current_time < morning:
        return "non_trading"

    return "rest"


async def _fetch_latest_trading_day() -> Optional[str]:
    url = f"http://{settings.stock_api_host}:{settings.stock_api_port}/api/trading-calendar/latest-on-or-before"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {settings.stock_api_token}",
    }
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                url, headers=headers, params={"token": settings.stock_api_token}
            )
            response.raise_for_status()
            data = response.json()
            if data.get("code") == 200 and data.get("data"):
                return data["data"].get("tradeDate")
    except Exception as exc:
        logger.error("Failed to fetch latest trading day: %s", exc, exc_info=True)
    return None


def _query_ticks(
    stock_code: str, trade_date: str, last_time: Optional[str]
) -> List[Dict[str, Any]]:
    params = {"stock_code": stock_code, "trade_date": trade_date}
    query = (
        f"SELECT {_CLICKHOUSE_COLUMNS} "
        "FROM market_realtime_ticks "
        "WHERE ts_code = %(stock_code)s AND date = %(trade_date)s"
    )
    if last_time:
        query += " AND time > %(last_time)s"
        params["last_time"] = last_time
    query += " ORDER BY time ASC"

    try:
        rows = _ch_client.execute(query, params)
    except Exception as exc:
        _handle_clickhouse_exception(exc)
        return []

    return [_row_to_tick(row) for row in rows]


def _row_to_tick(row: Iterable[Any]) -> Dict[str, Any]:
    tick = dict(zip(_TICK_FIELDS, row))
    tick_time = tick.get("time")
    if isinstance(tick_time, (datetime, time)):
        tick["time"] = tick_time.strftime("%H:%M:%S")
    elif isinstance(tick_time, str) and tick_time:
        tick["time"] = _normalize_time_str(tick_time)
    tick_date = tick.get("date")
    if isinstance(tick_date, (datetime, date)):
        tick["date"] = tick_date.strftime("%Y-%m-%d")
    elif isinstance(tick_date, str) and tick_date:
        tick["date"] = _normalize_date_str(tick_date)
    return tick


def _normalize_time_str(raw: str) -> str:
    text = raw.strip()
    for fmt in ("%H:%M:%S", "%H:%M", "%H%M%S", "%H%M"):
        try:
            parsed = datetime.strptime(text, fmt)
            return parsed.strftime("%H:%M:%S")
        except ValueError:
            continue
    return text


def _normalize_date_str(raw: str) -> str:
    text = raw.strip().replace("/", "-")
    if len(text) == 8 and text.isdigit():
        text = f"{text[:4]}-{text[4:6]}-{text[6:]}"
    for fmt in ("%Y-%m-%d", "%Y%m%d"):
        try:
            parsed = datetime.strptime(text, fmt)
            return parsed.strftime("%Y-%m-%d")
        except ValueError:
            continue
    return text
def _handle_clickhouse_exception(exc: Exception) -> None:
    if hasattr(exc, "code"):
        logger.error(
            "ClickHouse query failed (code=%s): %s", getattr(exc, "code", "unknown"), exc
        )
        if getattr(exc, "code", None) == 232:  # INCOMPATIBLE_COLUMNS
            logger.error(
                "检测到 ClickHouse 字段类型与应用不一致，请核对 "
                "market_realtime_ticks.date/time 列类型并保持为 Date/DateTime。"
            )
    else:
        logger.error("ClickHouse query failed: %s", exc, exc_info=True)
