from __future__ import annotations

import json
from pathlib import Path

import asyncpg
from elasticsearch import AsyncElasticsearch
from elasticsearch import ApiError
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

from app.elasticsearch_dep import get_es
from app.postgres_dep import get_pg_conn


router = APIRouter(prefix="/demo", tags=["demo"])


_RESOURCES_DIR = Path(__file__).resolve().parent / "resources"
_PG_SCHEMA_PATH = _RESOURCES_DIR / "postgres_schema.sql"
_ES_INDEX_PATH = _RESOURCES_DIR / "es_index.json"

ES_INDEX_NAME = "items_demo"


class ItemCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=2000)
    price_cents: int = Field(default=0, ge=0)


class PharmacyCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    city: str | None = Field(default=None, max_length=200)


@router.post("/setup")
async def setup(
    conn: asyncpg.Connection = Depends(get_pg_conn),
    es: AsyncElasticsearch = Depends(get_es),
) -> dict[str, str]:
    """
    Creates the demo Postgres tables and the demo Elasticsearch index.
    Safe to call multiple times.
    """
    sql = _PG_SCHEMA_PATH.read_text(encoding="utf-8")
    await conn.execute(sql)

    # Avoid HEAD-based "exists" calls here; just try to create and ignore
    # "already exists" (400) for an idempotent setup.
    body = json.loads(_ES_INDEX_PATH.read_text(encoding="utf-8"))
    try:
        await es.indices.create(index=ES_INDEX_NAME, **body)
    except ApiError as e:
        # resource_already_exists_exception is returned as 400 in ES.
        if getattr(e, "meta", None) is not None and e.meta.status == 400:
            # If it already exists, that's fine; otherwise re-raise.
            err = getattr(e, "body", None) or getattr(e, "error", None)
            err_type = None
            if isinstance(err, dict):
                err_type = (err.get("error") or {}).get("type") or err.get("type")
            if err_type == "resource_already_exists_exception":
                pass
            else:
                raise
        else:
            raise

    return {"status": "ok"}


@router.post("/items")
async def create_item(
    payload: ItemCreate,
    conn: asyncpg.Connection = Depends(get_pg_conn),
) -> dict[str, int]:
    row = await conn.fetchrow(
        """
        INSERT INTO items (name, description, price_cents)
        VALUES ($1, $2, $3)
        RETURNING id
        """,
        payload.name,
        payload.description,
        payload.price_cents,
    )
    return {"id": int(row["id"])}


@router.get("/items")
async def list_items(
    limit: int = Query(50, ge=1, le=200),
    conn: asyncpg.Connection = Depends(get_pg_conn),
) -> list[dict]:
    rows = await conn.fetch(
        """
        SELECT id, name, description, price_cents, created_at
        FROM items
        ORDER BY id DESC
        LIMIT $1
        """,
        limit,
    )
    return [dict(r) for r in rows]


@router.post("/pharmacies")
async def create_pharmacy(
    payload: PharmacyCreate,
    conn: asyncpg.Connection = Depends(get_pg_conn),
) -> dict[str, int]:
    row = await conn.fetchrow(
        """
        INSERT INTO pharmacies (name, city)
        VALUES ($1, $2)
        RETURNING id
        """,
        payload.name,
        payload.city,
    )
    return {"id": int(row["id"])}


@router.get("/pharmacies")
async def list_pharmacies(
    limit: int = Query(50, ge=1, le=200),
    conn: asyncpg.Connection = Depends(get_pg_conn),
) -> list[dict]:
    rows = await conn.fetch(
        """
        SELECT id, name, city, created_at
        FROM pharmacies
        ORDER BY id DESC
        LIMIT $1
        """,
        limit,
    )
    return [dict(r) for r in rows]


@router.post("/index/item/{item_id}")
async def index_item(
    item_id: int,
    conn: asyncpg.Connection = Depends(get_pg_conn),
    es: AsyncElasticsearch = Depends(get_es),
) -> dict[str, str]:
    row = await conn.fetchrow(
        """
        SELECT id, name, description, price_cents, created_at
        FROM items
        WHERE id = $1
        """,
        item_id,
    )
    if row is None:
        return {"status": "not_found"}

    doc = dict(row)
    doc["kind"] = "item"

    await es.index(index=ES_INDEX_NAME, id=str(item_id), document=doc, refresh="wait_for")
    return {"status": "indexed"}


@router.get("/search")
async def search(
    q: str = Query(min_length=1, max_length=200),
    size: int = Query(10, ge=1, le=50),
    es: AsyncElasticsearch = Depends(get_es),
) -> dict:
    res = await es.search(
        index=ES_INDEX_NAME,
        size=size,
        query={
            "multi_match": {
                "query": q,
                "fields": ["name^2", "description"],
            }
        },
    )
    return res


