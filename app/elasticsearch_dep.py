from __future__ import annotations

import os

from elasticsearch import AsyncElasticsearch
from fastapi import Request


def _elasticsearch_url() -> str:
    # Example: "http://localhost:9200" or "https://user:pass@host:9243"
    return os.getenv("ELASTICSEARCH_URL", "http://localhost:9200")


def _elasticsearch_api_key() -> str | None:
    # If set, should look like "id:api_key" (Elastic format).
    value = os.getenv("ELASTICSEARCH_API_KEY")
    if value is None:
        return None
    value = value.strip()
    return value or None


async def init_es_client(app_state: object) -> None:
    """Create and store a shared AsyncElasticsearch client on app.state."""
    api_key = _elasticsearch_api_key()
    kwargs: dict = {"hosts": [_elasticsearch_url()]}
    # Important: don't pass `api_key=None` — that can result in a malformed Authorization header.
    if api_key is not None:
        kwargs["api_key"] = api_key
    client = AsyncElasticsearch(**kwargs)
    setattr(app_state, "es", client)


async def close_es_client(app_state: object) -> None:
    client: AsyncElasticsearch | None = getattr(app_state, "es", None)
    if client is not None:
        await client.close()


async def get_es(request: Request) -> AsyncElasticsearch:
    client: AsyncElasticsearch | None = getattr(request.app.state, "es", None)
    if client is None:
        raise RuntimeError("Elasticsearch client is not initialized (missing lifespan init).")
    return client


