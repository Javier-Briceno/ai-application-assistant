import asyncpg
import logging
from contextlib import asynccontextmanager
from backend.config import settings

log = logging.getLogger(__name__)
_pool: asyncpg.Pool | None = None


async def get_pool() -> asyncpg.Pool:
    global _pool
    if _pool is None:
        _pool = await asyncpg.create_pool(
            host=settings.db_host,
            port=settings.db_port,
            database=settings.db_name,
            user=settings.db_user,
            password=settings.db_password,
            min_size=2,
            max_size=10,
            # Recycle idle connections after 60 s so stale connections from a
            # Postgres restart are discarded before the next request uses them.
            max_inactive_connection_lifetime=60,
        )
    return _pool


@asynccontextmanager
async def get_conn():
    pool = await get_pool()
    async with pool.acquire() as conn:
        yield conn


async def close_pool() -> None:
    global _pool
    if _pool:
        await _pool.close()
        _pool = None


async def ping_db() -> bool:
    """Return True if the DB is reachable, False on any error.

    Used by /api/health.  Never raises — a failed ping returns False so the
    health endpoint can report degraded status without crashing.
    """
    try:
        pool = await get_pool()
        async with pool.acquire() as conn:
            await conn.execute("SELECT 1")
        return True
    except Exception as exc:
        log.warning("DB ping failed: %s", exc)
        return False


async def reset_pool() -> None:
    """Close the pool and allow lazy re-initialisation on the next request.

    Call this after a confirmed Postgres restart to discard all stale
    connections immediately rather than waiting for max_inactive_connection_lifetime.
    """
    await close_pool()
    log.info("DB pool reset — will reconnect on next request.")
