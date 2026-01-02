from __future__ import annotations

from contextlib import asynccontextmanager

from elasticsearch import AsyncElasticsearch
from fastapi import Depends, FastAPI, HTTPException

from app.elasticsearch_dep import close_es_client, get_es, init_es_client
from app.postgres_dep import close_pg_pool, init_pg_pool
from app.demo_endpoints import router as demo_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_pg_pool(app.state)
    await init_es_client(app.state)
    try:
        yield
    finally:
        await close_es_client(app.state)
        await close_pg_pool(app.state)


app = FastAPI(title="postgres-elasticsearch-multisink", lifespan=lifespan)

app.include_router(demo_router)


@app.get("/", tags=["meta"])
def root() -> dict[str, str]:
    return {"message": "ok"}


@app.get("/health", tags=["meta"])
def health() -> dict[str, str]:
    return {"status": "healthy"}


@app.get("/health/elasticsearch", tags=["meta"])
async def health_elasticsearch(es: AsyncElasticsearch = Depends(get_es)) -> dict:
    try:
        info = await es.info()
        return {
            "status": "healthy",
            "cluster_name": info.get("cluster_name"),
            "cluster_uuid": info.get("cluster_uuid"),
            "version": (info.get("version") or {}).get("number"),
        }
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=503, detail=f"Elasticsearch unavailable: {e!s}") from e


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)


