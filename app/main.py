from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.elasticsearch_dep import close_es_client, init_es_client
from app.postgres_dep import close_pg_pool, init_pg_pool


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


@app.get("/", tags=["meta"])
def root() -> dict[str, str]:
    return {"message": "ok"}


@app.get("/health", tags=["meta"])
def health() -> dict[str, str]:
    return {"status": "healthy"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)


