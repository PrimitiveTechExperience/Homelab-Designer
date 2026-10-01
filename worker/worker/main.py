"""arq worker entrypoint. Run with: arq worker.main.WorkerSettings

Workers write listings and price snapshots to the DB; the API only reads them.
"""

import asyncio
import logging
from typing import Any

import httpx
from arq import cron
from arq.connections import RedisSettings

from app.core.config import get_settings
from app.db.session import SessionLocal
from worker.ingest import store_listings
from worker.retailers.base import Retailer
from worker.retailers.bestbuy import BestBuy

logger = logging.getLogger(__name__)


async def ping(ctx: dict[str, Any]) -> str:
    """Smoke-test job to confirm the worker is consuming the queue."""
    return "pong"


def _store(raw: list[Any]) -> int:
    with SessionLocal() as db:
        return store_listings(db, raw)


async def ingest_retailers(ctx: dict[str, Any]) -> dict[str, int]:
    """Fetch every configured retailer and store listings + price snapshots.

    One retailer failing must not block the rest, so errors are logged per source.
    """
    settings = get_settings()
    results: dict[str, int] = {}
    async with httpx.AsyncClient(timeout=30) as client:
        retailers: list[Retailer] = []
        if settings.bestbuy_api_key:
            retailers.append(BestBuy(settings.bestbuy_api_key, client, cache=ctx.get("redis")))
        else:
            logger.info("BESTBUY_API_KEY not set; skipping Best Buy")

        for retailer in retailers:
            try:
                raw = await retailer.fetch()
                results[retailer.source] = await asyncio.to_thread(_store, raw)
            except Exception:
                logger.exception("Ingestion failed for %s", retailer.source)
    return results


class WorkerSettings:
    functions = [ping, ingest_retailers]
    cron_jobs = [cron(ingest_retailers, hour={0, 6, 12, 18}, minute=0, run_at_startup=False)]
    redis_settings = RedisSettings.from_dsn(get_settings().redis_url)
