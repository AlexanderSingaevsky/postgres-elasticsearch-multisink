from __future__ import annotations

import os
from typing import AsyncIterator

import asyncpg
from fastapi import Request


def _postgres_dsn() -> str:
    """
    Configure via either:
    - POSTGRES_DSN="postgresql://user:pass@host:5432/db"
    - or POSTGRES_HOST/PORT/DB/USER/PASSWORD
    """
    dsn = os.getenv("POSTGRES_DSN")
    if dsn:
        return dsn

    host = os.getenv("POSTGRES_HOST", "localhost")
    port = int(os.getenv("POSTGRES_PORT", "5432"))
    db = os.getenv("POSTGRES_DB", "postgres")
    user = os.getenv("POSTGRES_USER", "postgres")
    password = os.getenv("POSTGRES_PASSWORD", "postgres")
    return f"postgresql://{user}:{password}@{host}:{port}/{db}"


async def init_pg_pool(app_state: object) -> None:
    """Create and store a shared asyncpg pool on app.state."""
    pool = await asyncpg.create_pool(dsn=_postgres_dsn(), min_size=1, max_size=10)
    setattr(app_state, "pg_pool", pool)


async def close_pg_pool(app_state: object) -> None:
    pool = getattr(app_state, "pg_pool", None)
    if pool is not None:
        await pool.close()


async def get_pg_pool(request: Request) -> asyncpg.Pool:
    pool = getattr(request.app.state, "pg_pool", None)
    if pool is None:
        raise RuntimeError("Postgres pool is not initialized (missing lifespan init).")
    return pool


async def get_pg_conn(request: Request) -> AsyncIterator[asyncpg.Connection]:
    """
    FastAPI dependency that yields an acquired connection from the shared pool.

    Usage:
        async def handler(conn=Depends(get_pg_conn)): ...
    """
    pool = await get_pg_pool(request)
    async with pool.acquire() as conn:
        yield conn


