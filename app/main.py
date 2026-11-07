"""
AIM Network — Autonomous M2M API Hub (Main FastAPI Application).
Combines:
- Overseer Dashboard (/) & PIN-protected Emergency Stop (/api/admin/toggle-pause)
- Self-marketing AI discovery manifests (/llms.txt, /agents.json, /.well-known/agent.json)
- Autonomous Scout (/cron/discover)
- x402-protected M2M Data Endpoints (/api/v1/crypto-pulse & /api/v1/deep-market-report)
"""

import asyncio
from contextlib import asynccontextmanager
import time
from collections import defaultdict
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import settings
from app.database import init_db
from app.routers.api_v1 import router as api_v1_router
from app.routers.dashboard import router as dashboard_router
from app.routers.discovery import router as discovery_router
from app.services.scout import run_autonomous_scout


async def _autopilot_scout_loop(db_path: str | None) -> None:
    """Background loop that periodically runs the Autonomous Scout & Auto-Deployer."""
    while True:
        try:
            await run_autonomous_scout(db_path=db_path)
        except Exception:
            pass
        await asyncio.sleep(max(60, settings.SCOUT_INTERVAL_SECONDS))


@asynccontextmanager
async def lifespan(app: FastAPI):
    db_override = getattr(app.state, "db_path", None)
    init_db(db_override)
    scout_task = None
    if settings.SCOUT_AUTOPILOT_ENABLED:
        scout_task = asyncio.create_task(_autopilot_scout_loop(db_override))
    try:
        yield
    finally:
        if scout_task:
            scout_task.cancel()


def create_app(db_path: str | None = None) -> FastAPI:
    app = FastAPI(
        title=settings.PROJECT_NAME,
        version=settings.VERSION,
        description=(
            "Autonomous Machine-to-Machine (M2M) Data & Quantitative Intelligence Hub. "
            "Pay per request via HTTP 402 (x402 protocol) in USDC on Base Mainnet."
        ),
        lifespan=lifespan,
    )
    if db_path:
        app.state.db_path = db_path

    # In-memory sliding window rate limiter (Cloudflare CF-Connecting-IP aware)
    ip_hits: dict[str, list[float]] = defaultdict(list)

    @app.middleware("http")
    async def security_and_rate_limit_middleware(request: Request, call_next):
        client_ip = (
            request.headers.get("CF-Connecting-IP")
            or request.headers.get("X-Forwarded-For", "").split(",")[0].strip()
            or (request.client.host if request.client else "unknown")
        )
        now = time.monotonic()
        window = [t for t in ip_hits[client_ip] if (now - t) < 60.0]
        if len(window) >= settings.RATE_LIMIT_PER_MINUTE:
            return JSONResponse(
                status_code=429,
                content={
                    "error": "Too Many Requests",
                    "detail": f"Rate limit exceeded ({settings.RATE_LIMIT_PER_MINUTE} req/min).",
                },
            )
        window.append(now)
        ip_hits[client_ip] = window

        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "SAMEORIGIN"
        return response

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(dashboard_router)
    app.include_router(discovery_router)
    app.include_router(api_v1_router)

    @app.get("/health", tags=["System"])
    async def health_check():
        return {
            "status": "healthy",
            "wallet": settings.WALLET_ADDRESS,
            "network": "base-mainnet",
        }

    return app


app = create_app()
