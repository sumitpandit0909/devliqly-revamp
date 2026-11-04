import asyncio
import contextlib
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.config import get_settings
from app.db import get_engine
from app.queue import run_worker
from app.routers import auth, conversations, expo_events, health, members, meta_webhook, operator

STATIC_DIR = Path(__file__).parent / "static"

SECURITY_HEADERS = {
    "Content-Security-Policy": (
        "default-src 'self'; img-src 'self' data:; frame-ancestors 'none'; base-uri 'none'; form-action 'self'"
    ),
    "Referrer-Policy": "no-referrer",
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
}


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    worker = asyncio.create_task(run_worker()) if get_settings().worker_enabled else None
    yield
    if worker:
        worker.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await worker
    await get_engine().dispose()


def create_app() -> FastAPI:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)  # Its request logs would include message URLs
    settings = get_settings()
    production = settings.is_production
    app = FastAPI(
        title="Devliqly Platform",
        lifespan=lifespan,
        docs_url=None if production else "/docs",
        redoc_url=None,
        openapi_url=None if production else "/openapi.json",
    )

    if settings.cors_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.cors_origins,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    @app.middleware("http")
    async def add_security_headers(request: Request, call_next) -> Response:
        response = await call_next(request)
        for name, value in SECURITY_HEADERS.items():
            # The local API docs load their assets from a CDN
            if name == "Content-Security-Policy" and request.url.path == "/docs":
                continue
            response.headers[name] = value
        if production:
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        if request.url.path.startswith("/api/"):
            response.headers["Cache-Control"] = "no-store"
        return response

    app.include_router(health.router)
    app.include_router(auth.router)
    app.include_router(operator.router)
    app.include_router(members.router)
    app.include_router(expo_events.router)
    app.include_router(conversations.router)
    app.include_router(meta_webhook.router)
    app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="site")
    return app


app = create_app()
