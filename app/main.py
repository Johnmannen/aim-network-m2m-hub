"""
AIM Network - Autonomous M2M API Hub (Main FastAPI Application).
Combines:
- Overseer Dashboard (/) & PIN-protected Emergency Stop (/api/admin/toggle-pause)
- Self-marketing AI discovery manifests (/llms.txt, /agents.json, /.well-known/agent.json, /mcp)
- Autonomous Scout (/cron/discover)
- x402-protected M2M Data Endpoints (/api/v1/crypto-pulse, /api/v1/base-dex-radar, /api/v1/deep-market-report)
"""

import asyncio
from collections import defaultdict
from contextlib import asynccontextmanager
import logging
import time
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import httpx

from app.config import settings
from app.utils import resolve_client_ip
from app.database import init_db, log_traffic_event
from app.routers.api_v1 import router as api_v1_router
from app.routers.dashboard import router as dashboard_router
from app.routers.discovery import router as discovery_router
from app.services.cloud_backup import push_to_cloud_gist, restore_from_cloud_gist
from app.services.scout import run_autonomous_scout

logger = logging.getLogger(__name__)


async def _autopilot_scout_loop(db_path: str | None) -> None:
    """Background loop that periodically runs the Autonomous Scout & Cloud Backup."""
    if not settings.TESTING:
        await restore_from_cloud_gist(db_path=db_path)
    while True:
        try:
            await run_autonomous_scout(db_path=db_path)
            if not settings.TESTING:
                await push_to_cloud_gist(db_path=db_path)
        except Exception as exc:
            logger.exception("Autonomous Scout background loop error: %s", exc)
        await asyncio.sleep(max(60, settings.SCOUT_INTERVAL_SECONDS))


@asynccontextmanager
async def lifespan(app: FastAPI):
    db_override = getattr(app.state, "db_path", None)
    init_db(db_override)
    app.state.http_client = httpx.AsyncClient(timeout=5.0)
    scout_task = None
    if settings.SCOUT_AUTOPILOT_ENABLED:
        scout_task = asyncio.create_task(_autopilot_scout_loop(db_override))
    try:
        yield
    finally:
        if scout_task:
            scout_task.cancel()
        await app.state.http_client.aclose()


_resolve_client_ip = resolve_client_ip


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

    # Bounded sliding-window rate limiter (prevents memory leaks via periodic pruning)
    ip_hits: dict[str, list[float]] = defaultdict(list)
    last_prune_ts: list[float] = [time.monotonic()]

    @app.middleware("http")
    async def security_and_rate_limit_middleware(request: Request, call_next):
        t0 = time.perf_counter()
        client_ip = _resolve_client_ip(request)
        country = request.headers.get("CF-IPCountry", "GLOBAL")
        user_agent = request.headers.get("User-Agent", "")
        has_admin_cookie = bool(request.cookies.get("aim_admin"))
        db_override = getattr(request.app.state, "db_path", None)

        now = time.monotonic()
        # Prune stale IP keys every 120 seconds or if map exceeds 2,000 keys
        if (now - last_prune_ts[0]) > 120.0 or len(ip_hits) > 2000:
            stale_ips = [
                ip
                for ip, timestamps in ip_hits.items()
                if not timestamps or (now - timestamps[-1]) >= 60.0
            ]
            for ip in stale_ips:
                ip_hits.pop(ip, None)
            last_prune_ts[0] = now

        window = [t for t in ip_hits[client_ip] if (now - t) < 60.0]
        if len(window) >= settings.RATE_LIMIT_PER_MINUTE:
            elapsed_ms = (time.perf_counter() - t0) * 1000.0
            try:
                log_traffic_event(
                    path=request.url.path,
                    method=request.method,
                    status_code=429,
                    user_agent=user_agent,
                    country=country,
                    latency_ms=elapsed_ms,
                    has_admin_cookie=has_admin_cookie,
                    db_path=db_override,
                )
            except Exception as exc:
                logger.warning("Traffic logging failed on 429: %s", exc)
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
        elapsed_ms = (time.perf_counter() - t0) * 1000.0
        try:
            log_traffic_event(
                path=request.url.path,
                method=request.method,
                status_code=response.status_code,
                user_agent=user_agent,
                country=country,
                latency_ms=elapsed_ms,
                has_admin_cookie=has_admin_cookie,
                db_path=db_override,
            )
        except Exception as exc:
            logger.warning("Traffic logging failed: %s", exc)

        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "SAMEORIGIN"
        return response

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["Content-Type", "X-PAYMENT-PROOF", "X-Admin-Pin", "X-Scout-Token"],
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
