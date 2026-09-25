"""arq worker entrypoint. Run with: arq worker.main.WorkerSettings

Workers write listings and price snapshots to the DB; the API only reads them.
"""

from typing import Any

from arq.connections import RedisSettings

from app.core.config import get_settings


async def ping(ctx: dict[str, Any]) -> str:
    """Smoke-test job to confirm the worker is consuming the queue."""
    return "pong"


class WorkerSettings:
    functions = [ping]
    # Scheduled ingestion jobs (e.g. eBay Browse API pulls) go here as arq cron jobs.
    cron_jobs: list[Any] = []
    redis_settings = RedisSettings.from_dsn(get_settings().redis_url)
