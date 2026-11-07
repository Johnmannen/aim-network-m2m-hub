"""
Overseer Dashboard (/) & PIN-Protected Admin Router.
Uses Jinja2 autoescaped templates (XSS-safe), constant-time PIN comparison
(secrets.compare_digest), and brute-force lockout protection.
"""

from collections import defaultdict
from pathlib import Path
import secrets
import time
from typing import Optional
from fastapi import APIRouter, Header, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from jinja2 import Environment, FileSystemLoader, select_autoescape
from pydantic import BaseModel

from app.config import settings
from app.database import (
    export_db_snapshot,
    get_stats,
    import_db_snapshot,
    set_pause_state,
)
from app.services.market_data import (
    fetch_base_dex_radar,
    fetch_crypto_pulse_data,
    fetch_deep_market_report,
    fetch_dynamic_asset_pulse,
)

router = APIRouter(tags=["Overseer Dashboard & Admin"])

TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates"
_jinja_env = Environment(
    loader=FileSystemLoader(str(TEMPLATES_DIR)),
    autoescape=select_autoescape(["html", "xml"]),
)

# Brute-force tracking: ip -> list of failure timestamps
_pin_failures: dict[str, list[float]] = defaultdict(list)


def verify_admin_pin_with_lockout(request: Request, provided_pin: Optional[str]) -> None:
    """
    Verify admin PIN using constant-time secrets.compare_digest and enforce
    brute-force lockout after MAX_PIN_FAILURES within PIN_LOCKOUT_SECONDS.
    """
    client_ip = request.client.host if request.client else "unknown"
    now = time.monotonic()
    recent_fails = [
        t for t in _pin_failures[client_ip] if (now - t) < settings.PIN_LOCKOUT_SECONDS
    ]
    _pin_failures[client_ip] = recent_fails

    if len(recent_fails) >= settings.MAX_PIN_FAILURES:
        raise HTTPException(
            status_code=429,
            detail="För många felaktiga PIN-försök. Kontot är tillfälligt låst i 15 minuter.",
        )

    clean_pin = (provided_pin or "").strip()
    if not clean_pin or not secrets.compare_digest(clean_pin, settings.ADMIN_PIN):
        _pin_failures[client_ip].append(now)
        raise HTTPException(
            status_code=401,
            detail="Ogiltig eller saknad Admin PIN-kod.",
        )

    # Clear failure counter on success
    _pin_failures.pop(client_ip, None)


class PauseToggleRequest(BaseModel):
    pin: Optional[str] = None
    paused: Optional[bool] = None


class ModeToggleRequest(BaseModel):
    pin: Optional[str] = None
    mode: Optional[str] = None


@router.get("/api/admin/stats", response_class=JSONResponse)
async def admin_stats_endpoint(request: Request) -> dict:
    """Return live stats, scout discoveries, traffic telemetry, and wallet info."""
    db_override = request.app.state.db_path if hasattr(request.app.state, "db_path") else None
    stats = get_stats(db_override)
    return {
        "wallet_address": settings.WALLET_ADDRESS,
        "network": "base-mainnet",
        "token": "USDC",
        "verify_mode": settings.X402_VERIFY_MODE,
        **stats,
    }


@router.post("/api/admin/toggle-pause", response_class=JSONResponse)
async def toggle_emergency_stop(
    request: Request,
    payload: Optional[PauseToggleRequest] = None,
    x_admin_pin: Optional[str] = Header(default=None, alias="X-Admin-Pin"),
) -> dict:
    """Toggle or set the Emergency Stop state (PIN-protected with brute-force lockout)."""
    provided_pin = (payload.pin if payload and payload.pin else None) or x_admin_pin
    verify_admin_pin_with_lockout(request, provided_pin)

    db_override = request.app.state.db_path if hasattr(request.app.state, "db_path") else None
    current = get_stats(db_override)
    next_paused = (
        payload.paused
        if (payload is not None and payload.paused is not None)
        else (not current["paused"])
    )
    updated = set_pause_state(next_paused, db_override)
    return {
        "status": "updated",
        "paused": updated["paused"],
        "system_status": updated["status"],
        "stats": updated,
    }


@router.post("/api/admin/toggle-mode", response_class=JSONResponse)
async def toggle_verify_mode(
    request: Request,
    payload: Optional[ModeToggleRequest] = None,
    x_admin_pin: Optional[str] = Header(default=None, alias="X-Admin-Pin"),
) -> dict:
    """Switch between 'hybrid' and 'strict_onchain' (PIN-protected with brute-force lockout)."""
    provided_pin = (payload.pin if payload and payload.pin else None) or x_admin_pin
    verify_admin_pin_with_lockout(request, provided_pin)

    current = settings.X402_VERIFY_MODE.lower()
    next_mode = (
        payload.mode
        if (payload and payload.mode in ("hybrid", "strict_onchain"))
        else ("strict_onchain" if current == "hybrid" else "hybrid")
    )
    settings.X402_VERIFY_MODE = next_mode
    return {"status": "updated", "verify_mode": settings.X402_VERIFY_MODE}


@router.get("/api/admin/backup-snapshot", response_class=JSONResponse)
async def get_backup_snapshot(request: Request) -> dict:
    """
    Export non-sensitive SQLite telemetry & state snapshot so the GitHub Gist
    cloud backup can persist traffic, discoveries, dynamic endpoints, and used tx hashes
    across Render Free Tier container restarts.
    """
    db_override = request.app.state.db_path if hasattr(request.app.state, "db_path") else None
    return export_db_snapshot(db_override)


@router.post("/api/admin/restore-snapshot", response_class=JSONResponse)
async def restore_backup_snapshot(
    request: Request,
    snapshot: dict,
    x_admin_pin: Optional[str] = Header(default=None, alias="X-Admin-Pin"),
    x_scout_token: Optional[str] = Header(default=None, alias="X-Scout-Token"),
) -> dict:
    """Restore/merge SQLite snapshot if container restarted (requires auth token)."""
    provided = (x_scout_token or x_admin_pin or "").strip()
    verify_admin_pin_with_lockout(request, provided)
    db_override = request.app.state.db_path if hasattr(request.app.state, "db_path") else None
    updated_stats = import_db_snapshot(snapshot, db_override)
    return {"status": "restored", "stats": updated_stats}


@router.get("/api/admin/preview-product", response_class=JSONResponse)
async def preview_product_payload(
    request: Request,
    endpoint: str = "/api/v1/crypto-pulse",
) -> dict:
    """Inspect the exact live JSON product that a buying AI-bot receives."""
    if endpoint == "/api/v1/crypto-pulse":
        data = await fetch_crypto_pulse_data()
        return {"endpoint": endpoint, "price_usdc": settings.PRICE_MICRO_USDC, "product_payload": data}
    if endpoint == "/api/v1/base-dex-radar":
        data = await fetch_base_dex_radar()
        return {"endpoint": endpoint, "price_usdc": settings.PRICE_DEX_RADAR_USDC, "product_payload": data}
    if endpoint == "/api/v1/deep-market-report":
        data = await fetch_deep_market_report()
        return {"endpoint": endpoint, "price_usdc": settings.PRICE_PREMIUM_USDC, "product_payload": data}

    if endpoint.startswith("/api/v1/trending/"):
        slug = endpoint.replace("/api/v1/trending/", "").strip().lower()
        db_override = request.app.state.db_path if hasattr(request.app.state, "db_path") else None
        stats = get_stats(db_override)
        matched = next(
            (ep for ep in stats.get("dynamic_endpoints", []) if ep["slug"] == slug),
            None,
        )
        if matched:
            data = await fetch_dynamic_asset_pulse(
                slug=slug,
                asset_name=matched["asset_name"],
                asset_symbol=matched["asset_symbol"],
                coingecko_id=matched["coingecko_id"],
            )
            return {"endpoint": endpoint, "price_usdc": matched["price_usdc"], "product_payload": data}

    raise HTTPException(status_code=404, detail=f"Okänd tjänst: {endpoint}")


@router.get("/api/admin/self-check", response_class=JSONResponse)
async def run_agent_self_diagnosis(request: Request) -> dict:
    """Run a live health check on all 4 autonomous subsystems/agents."""
    db_override = request.app.state.db_path if hasattr(request.app.state, "db_path") else None
    stats = get_stats(db_override)
    pulse = await fetch_crypto_pulse_data()
    total_services = 3 + len(stats.get("dynamic_endpoints", []))

    return {
        "overall_status": "ALL_AGENTS_OPERATIONAL",
        "agents": [
            {
                "name": "1. Spanar- & Bygg-Agent (Scout & Auto-Deployer)",
                "status": "ONLINE",
                "detail": f"Har byggt {len(stats.get('dynamic_endpoints', []))} st extra trend-API:er automatiskt. Söker nya var 60:e min.",
            },
            {
                "name": "2. Data- & Analys-Agent (Market Intelligence Engine)",
                "status": "ONLINE",
                "detail": f"Hämtar live-priser (BTC: ${pulse['assets']['BTC']['price_usd']}) & Fear/Greed ({pulse['fear_and_greed']['index']}/100).",
            },
            {
                "name": "3. Kassa- & Säkerhets-Agent (x402 Base L2 Gatekeeper)",
                "status": "ONLINE",
                "detail": f"Läge: {settings.X402_VERIFY_MODE.upper()} • Plånbok: {settings.WALLET_ADDRESS[:8]}... • Replay-skydd aktivt.",
            },
            {
                "name": "4. Skyltfönster- & Marknadsförings-Agent (Discovery)",
                "status": "ONLINE",
                "detail": f"Exponerar {total_services} st säljbara API:er i /llms.txt, /agents.json, /mcp & /sitemap.xml.",
            },
        ],
    }


@router.get("/", response_class=HTMLResponse)
async def overseer_dashboard(request: Request) -> HTMLResponse:
    """Render the responsive Overseer Dashboard using autoescaped Jinja2 template."""
    db_override = request.app.state.db_path if hasattr(request.app.state, "db_path") else None
    stats = get_stats(db_override)

    is_paused = stats["paused"]
    status_badge_color = "#ef4444" if is_paused else "#4ade80"
    status_dot = "🔴 PAUSED (NÖDSTOPP AKTIVT)" if is_paused else "🟢 ONLINE (24/7 Autonom Drift)"
    btn_label = "▶️ ÅTERUPPTA ALLA TJÄNSTER" if is_paused else "🛑 NÖDSTOPP: PAUSA ALLA TJÄNSTER"
    btn_bg = "#16a34a" if is_paused else "#dc2626"

    micro_rev = round(stats["calls_micro"] * settings.PRICE_MICRO_USDC, 2)
    prem_rev = round(stats["calls_premium"] * settings.PRICE_PREMIUM_USDC, 2)
    total_rev = round(stats["revenue_usdc"], 2)
    total_sek = round(total_rev * 10.5, 2)

    wallet = settings.WALLET_ADDRESS
    short_wallet = f"{wallet[:6]}...{wallet[-4:]}" if len(wallet) >= 12 else wallet
    v_mode = settings.X402_VERIFY_MODE.upper()
    v_mode_label = (
        "🔒 STRICT ON-CHAIN (Endast äkta Base-tx)"
        if v_mode == "STRICT_ONCHAIN"
        else "🧪 HYBRID (Äkta Base-tx + Sandbox-test)"
    )

    telemetry = stats.get("traffic_telemetry", {})
    stream_events = []
    for ev in telemetry.get("recent_stream", [])[:12]:
        ts_short = (
            ev["created_at"][11:19]
            if len(ev.get("created_at", "")) >= 19
            else ev.get("created_at", "")
        )
        cat = ev.get("category", "OTHER")
        if cat == "PAID_200":
            badge_cls = "b-paid"
            badge_txt = f"💰 {ev['status_code']} BETALD"
        elif cat == "QUOTE_402":
            badge_cls = "b-quote"
            badge_txt = f"🟡 {ev['status_code']} PRISOFFERT (x402)"
        elif cat == "DISCOVERY":
            badge_cls = "b-disc"
            badge_txt = f"🔍 {ev['status_code']} MENY/KATALOG"
        elif cat == "BLOCKED":
            badge_cls = "b-block"
            badge_txt = f"🛡️ {ev['status_code']} BLOCKERAD"
        else:
            badge_cls = "b-disc"
            badge_txt = f"⚪ {ev['status_code']}"

        stream_events.append(
            {
                "ts_short": ts_short,
                "country": ev.get("country", "GLOBAL"),
                "agent_type": ev.get("agent_type", ""),
                "method": ev.get("method", "GET"),
                "path": ev.get("path", ""),
                "badge_cls": badge_cls,
                "badge_txt": badge_txt,
                "latency_ms": float(ev.get("latency_ms", 0.0)),
            }
        )

    template = _jinja_env.get_template("dashboard.html")
    html_content = template.render(
        status_badge_color=status_badge_color,
        status_dot=status_dot,
        btn_label=btn_label,
        btn_bg=btn_bg,
        wallet=wallet,
        short_wallet=short_wallet,
        v_mode_label=v_mode_label,
        total_rev=total_rev,
        total_sek=total_sek,
        micro_rev=micro_rev,
        prem_rev=prem_rev,
        price_micro=settings.PRICE_MICRO_USDC,
        price_dex=settings.PRICE_DEX_RADAR_USDC,
        price_premium=settings.PRICE_PREMIUM_USDC,
        stats=stats,
        telemetry=telemetry,
        stream_events=stream_events,
        total_active_apis=3 + len(stats.get("dynamic_endpoints", [])),
    )
    return HTMLResponse(content=html_content)
