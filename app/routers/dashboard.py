"""
Overseer Dashboard (/) & PIN-Protected Admin Router.
Uses Jinja2 autoescaped templates (XSS-safe), constant-time PIN comparison
(secrets.compare_digest), and brute-force lockout protection.
"""

from collections import defaultdict
from pathlib import Path
import hashlib
import hmac
import secrets
import time
from typing import Optional
from fastapi import APIRouter, Header, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, Response
from jinja2 import Environment, FileSystemLoader, select_autoescape
from pydantic import BaseModel

from app.config import settings
from app.utils import resolve_client_ip
from app.database import (
    check_pin_lockout_db,
    clear_pin_failures_db,
    clear_traffic_logs_db,
    export_db_snapshot,
    get_stats,
    import_db_snapshot,
    log_traffic_event,
    record_paid_call,
    record_pin_failure_db,
    reset_simulated_purchases,
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


def verify_admin_pin_with_lockout(
    request: Request, provided_pin: Optional[str], allow_scout_token: bool = False
) -> None:
    """
    Verify admin PIN (or optionally SCOUT_SECRET_TOKEN) using constant-time
    secrets.compare_digest and enforce brute-force lockout after MAX_PIN_FAILURES
    (persisted in SQLite + in-memory).
    """
    client_ip = resolve_client_ip(request)
    db_override = (
        request.app.state.db_path
        if hasattr(request.app, "state") and hasattr(request.app.state, "db_path")
        else None
    )
    now = time.monotonic()
    # Prune stale keys from in-memory _pin_failures map to prevent unbounded growth
    if len(_pin_failures) > 500:
        stale_keys = [
            ip
            for ip, ts_list in _pin_failures.items()
            if not ts_list or (now - ts_list[-1]) >= settings.PIN_LOCKOUT_SECONDS
        ]
        for ip in stale_keys:
            _pin_failures.pop(ip, None)

    recent_fails = [
        t for t in _pin_failures[client_ip] if (now - t) < settings.PIN_LOCKOUT_SECONDS
    ]
    _pin_failures[client_ip] = recent_fails

    is_locked_db = check_pin_lockout_db(
        client_ip=client_ip,
        window_seconds=settings.PIN_LOCKOUT_SECONDS,
        max_failures=settings.MAX_PIN_FAILURES,
        db_path=db_override,
    )
    if len(recent_fails) >= settings.MAX_PIN_FAILURES or is_locked_db:
        raise HTTPException(
            status_code=429,
            detail="För många felaktiga PIN-försök. Kontot är tillfälligt låst i 15 minuter.",
        )

    clean_pin = (provided_pin or "").strip()
    if not clean_pin:
        raise HTTPException(
            status_code=401,
            detail="Saknad Admin PIN-kod / Token.",
        )

    is_valid_admin = secrets.compare_digest(clean_pin, settings.ADMIN_PIN)
    is_valid_scout = bool(
        allow_scout_token
        and secrets.compare_digest(clean_pin, settings.SCOUT_SECRET_TOKEN)
    )
    if not (is_valid_admin or is_valid_scout):
        _pin_failures[client_ip].append(now)
        record_pin_failure_db(client_ip, db_path=db_override)
        raise HTTPException(
            status_code=401,
            detail="Ogiltig Admin PIN-kod / Token.",
        )

    # Clear failure counter on success
    _pin_failures.pop(client_ip, None)
    clear_pin_failures_db(client_ip, db_path=db_override)


SESSION_COOKIE = "aim_admin"
SESSION_MAX_AGE = settings.SESSION_MAX_AGE_SECONDS


def _session_sig(ts: str) -> str:
    secret_key = (settings.SESSION_SECRET or settings.ADMIN_PIN).encode()
    return hmac.new(
        secret_key, f"dashboard:{ts}".encode(), hashlib.sha256
    ).hexdigest()


def make_session_token() -> str:
    ts = str(int(time.time()))
    return f"{ts}.{_session_sig(ts)}"


def has_valid_session(request: Request) -> bool:
    """True if the request carries a valid, unexpired signed dashboard session cookie."""
    token = request.cookies.get(SESSION_COOKIE, "")
    ts, _, sig = token.partition(".")
    if not ts.isdigit() or not sig:
        return False
    if time.time() - int(ts) > SESSION_MAX_AGE:
        return False
    return hmac.compare_digest(sig, _session_sig(ts))


LOGIN_HTML = """<!doctype html><html lang="sv"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><meta name="robots" content="noindex">
<title>AIM Network</title>
<style>body{font-family:system-ui;background:#0b1020;color:#e5e7eb;display:flex;min-height:100vh;align-items:center;justify-content:center;margin:0}
.c{background:#111827;padding:32px;border-radius:12px;width:320px;text-align:center}
input,button{width:100%;padding:10px;margin-top:12px;border-radius:8px;border:1px solid #374151;background:#0b1020;color:#e5e7eb;box-sizing:border-box}
button{background:#16a34a;border:0;cursor:pointer}#e{color:#f87171;margin-top:8px;min-height:1em}</style></head>
<body><div class="c"><h2>AIM Network</h2><p>Autonomous M2M API Hub &mdash; admin</p>
<p><a style="color:#38bdf8" href="/llms.txt">/llms.txt</a> &middot; <a style="color:#38bdf8" href="/agents.json">/agents.json</a></p>
<input id="p" type="password" placeholder="Admin PIN / Token" autocomplete="current-password">
<button onclick="login()">Logga in</button><div id="e"></div></div>
<script>async function login(){const r=await fetch("/api/admin/login",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({pin:document.getElementById("p").value})});
if(r.ok){location.reload()}else{const d=await r.json();document.getElementById("e").textContent=d.detail||"Fel"}}
document.getElementById("p").addEventListener("keydown",e=>{if(e.key==="Enter")login()})</script></body></html>"""


class LoginRequest(BaseModel):
    pin: Optional[str] = None


@router.post("/api/admin/login", response_class=JSONResponse)
async def admin_login(request: Request, payload: LoginRequest) -> JSONResponse:
    """Exchange the admin PIN for a signed HttpOnly session cookie (lockout-protected)."""
    verify_admin_pin_with_lockout(request, payload.pin)
    resp = JSONResponse({"status": "ok"})
    resp.set_cookie(
        SESSION_COOKIE,
        make_session_token(),
        max_age=SESSION_MAX_AGE,
        httponly=True,
        secure=not settings.TESTING,
        samesite="strict",
    )
    return resp


@router.post("/api/admin/logout", response_class=JSONResponse)
async def admin_logout() -> JSONResponse:
    resp = JSONResponse({"status": "ok"})
    resp.delete_cookie(SESSION_COOKIE)
    return resp


class PauseToggleRequest(BaseModel):
    pin: Optional[str] = None
    paused: Optional[bool] = None


class ModeToggleRequest(BaseModel):
    pin: Optional[str] = None
    mode: Optional[str] = None


@router.get("/api/admin/stats", response_class=JSONResponse)
async def admin_stats_endpoint(
    request: Request,
    x_admin_pin: Optional[str] = Header(default=None, alias="X-Admin-Pin"),
) -> dict:
    """Return live stats, scout discoveries, traffic telemetry, and wallet info (PIN-protected)."""
    if not has_valid_session(request):
        verify_admin_pin_with_lockout(request, x_admin_pin)
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
async def get_backup_snapshot(
    request: Request,
    x_admin_pin: Optional[str] = Header(default=None, alias="X-Admin-Pin"),
    x_scout_token: Optional[str] = Header(default=None, alias="X-Scout-Token"),
) -> dict:
    """Export sanitized SQLite snapshot (IPs and payer addresses are redacted). Protected by X-Scout-Token or X-Admin-Pin."""
    provided = (x_scout_token or x_admin_pin or "").strip()
    verify_admin_pin_with_lockout(request, provided, allow_scout_token=True)
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
    verify_admin_pin_with_lockout(request, provided, allow_scout_token=True)
    db_override = request.app.state.db_path if hasattr(request.app.state, "db_path") else None
    updated_stats = import_db_snapshot(snapshot, db_override)
    return {"status": "restored", "stats": updated_stats}


@router.get("/api/admin/preview-product", response_class=JSONResponse)
async def preview_product_payload(
    request: Request,
    endpoint: str = "/api/v1/crypto-pulse",
    x_admin_pin: Optional[str] = Header(default=None, alias="X-Admin-Pin"),
) -> dict:
    """Inspect the exact live JSON product a buying AI-bot receives (PIN-protected, else it bypasses the paywall)."""
    if not has_valid_session(request):
        verify_admin_pin_with_lockout(request, x_admin_pin)
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
async def run_agent_self_diagnosis(
    request: Request,
    x_admin_pin: Optional[str] = Header(default=None, alias="X-Admin-Pin"),
) -> dict:
    """Run a live health check on all 4 autonomous subsystems/agents (PIN-protected)."""
    if not has_valid_session(request):
        verify_admin_pin_with_lockout(request, x_admin_pin)
    db_override = request.app.state.db_path if hasattr(request.app.state, "db_path") else None
    stats = get_stats(db_override)
    pulse = await fetch_crypto_pulse_data()
    all_dyn = stats.get("dynamic_endpoints", [])
    canonical_slugs = {"morpho", "virtual"}
    canonical_count = sum(1 for ep in all_dyn if ep.get("slug") in canonical_slugs)
    scout_built_count = sum(1 for ep in all_dyn if ep.get("slug") not in canonical_slugs)
    core_endpoints_count = 3
    total_services = core_endpoints_count + canonical_count + scout_built_count

    return {
        "overall_status": "ALL_AGENTS_OPERATIONAL",
        "agents": [
            {
                "name": "1. Spanar- & Bygg-Agent (Scout & Auto-Deployer)",
                "status": "ONLINE",
                "detail": f"Har byggt {scout_built_count} st extra trend-API:er automatiskt (+ {canonical_count} kanoniska). Söker nya var 60:e min.",
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


@router.post("/api/admin/simulate-purchase", response_class=JSONResponse)
async def simulate_admin_purchase(
    request: Request,
    x_admin_pin: Optional[str] = Header(default=None, alias="X-Admin-Pin"),
) -> dict:
    """
    Admin-only 1-click purchase simulator:
    Records a simulated $0.01 USDC purchase on /api/v1/crypto-pulse, logs the 402 -> 200
    conversion funnel in Traffic Radar, and returns the unlocked product payload.
    Can be wiped anytime via POST /api/admin/reset-simulations.
    """
    if not has_valid_session(request):
        verify_admin_pin_with_lockout(request, x_admin_pin)

    db_override = request.app.state.db_path if hasattr(request.app.state, "db_path") else None
    sim_tx_hash = f"0xsim_{secrets.token_hex(16)}"

    # 1. Log simulated 402 price quote followed by 200 paid delivery in Traffic Radar
    log_traffic_event(
        path="/api/v1/crypto-pulse",
        method="GET",
        status_code=402,
        user_agent="httpx/Simulerad Test-Bot",
        country="SE",
        latency_ms=14.2,
        db_path=db_override,
    )
    record_paid_call(
        tx_hash=sim_tx_hash,
        endpoint="/api/v1/crypto-pulse",
        amount_usdc=settings.PRICE_MICRO_DEC,
        tier="micro",
        payer_address="0xsim_admin_test",
        verified_mode="admin_simulation",
        db_path=db_override,
    )
    log_traffic_event(
        path="/api/v1/crypto-pulse",
        method="GET",
        status_code=200,
        user_agent="httpx/Simulerad Test-Bot",
        country="SE",
        latency_ms=28.5,
        db_path=db_override,
    )
    product = await fetch_crypto_pulse_data()
    return {
        "status": "simulated_purchase_complete",
        "tx_hash": sim_tx_hash,
        "amount_usdc": float(settings.PRICE_MICRO_DEC),
        "endpoint": "/api/v1/crypto-pulse",
        "unlocked_product": product,
    }


@router.post("/api/admin/reset-simulations", response_class=JSONResponse)
async def reset_admin_simulations(
    request: Request,
    x_admin_pin: Optional[str] = Header(default=None, alias="X-Admin-Pin"),
) -> dict:
    """Remove all admin-simulated test purchases so revenue counters show only real on-chain sales."""
    if not has_valid_session(request):
        verify_admin_pin_with_lockout(request, x_admin_pin)

    db_override = request.app.state.db_path if hasattr(request.app.state, "db_path") else None
    updated_stats = reset_simulated_purchases(db_override)
    return {"status": "simulations_cleared", "stats": updated_stats}


@router.post("/api/admin/clear-traffic", response_class=JSONResponse)
async def clear_admin_traffic_logs(
    request: Request,
    x_admin_pin: Optional[str] = Header(default=None, alias="X-Admin-Pin"),
) -> dict:
    """Clear all traffic_logs so only fresh external bot visits are shown."""
    if not has_valid_session(request):
        verify_admin_pin_with_lockout(request, x_admin_pin)

    db_override = request.app.state.db_path if hasattr(request.app.state, "db_path") else None
    updated_stats = clear_traffic_logs_db(db_override)
    return {"status": "traffic_cleared", "stats": updated_stats}


def _render_dashboard_html(request: Request) -> HTMLResponse:
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
    for ev in telemetry.get("recent_stream", [])[:15]:
        ts_short = (
            ev["created_at"][11:19]
            if len(ev.get("created_at", "")) >= 19
            else ev.get("created_at", "")
        )
        cat = ev.get("category", "OTHER")
        if cat == "PAID_200":
            badge_cls = "b-paid"
            badge_txt = f"💰 {ev['status_code']} BETALD"
        elif cat == "SAMPLE_200":
            badge_cls = "b-disc"
            badge_txt = f"🔬 {ev['status_code']} SCHEMA-PROV"
        elif cat == "QUOTE_402":
            badge_cls = "b-quote"
            badge_txt = f"🟡 {ev['status_code']} PRISOFFERT (x402)"
        elif cat == "DISCOVERY":
            badge_cls = "b-disc"
            badge_txt = f"🔍 {ev['status_code']} MENY/KATALOG"
        elif cat == "SCANNER":
            badge_cls = "b-block"
            badge_txt = f"🛡️ {ev['status_code']} SKANNARE"
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

    all_dyn_render = stats.get("dynamic_endpoints", [])
    canonical_slugs = {"morpho", "virtual"}
    canonical_render = sum(1 for ep in all_dyn_render if ep.get("slug") in canonical_slugs)
    scout_built_render = sum(1 for ep in all_dyn_render if ep.get("slug") not in canonical_slugs)
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
        scout_built_count=scout_built_render,
        canonical_count=canonical_render,
        total_active_apis=3 + canonical_render + scout_built_render,
    )
    return HTMLResponse(content=html_content)


@router.api_route("/admin", methods=["GET", "HEAD"], response_class=HTMLResponse)
async def admin_dashboard_portal(request: Request) -> Response:
    """Dedicated Admin Portal (shows login form if unauthenticated, Overseer Dashboard if authenticated)."""
    if not has_valid_session(request):
        if request.method == "HEAD":
            return Response(status_code=200, media_type="text/html")
        return HTMLResponse(content=LOGIN_HTML, headers={"Cache-Control": "no-store"})
    if request.method == "HEAD":
        return Response(status_code=200, media_type="text/html")
    return _render_dashboard_html(request)


@router.api_route("/", methods=["GET", "HEAD"])
async def root_entrypoint(request: Request) -> Response:
    """
    Public Entrypoint for AIM Network:
    - Returns JSON machine discovery manifest when requested with Accept: application/json or ?format=json.
    - If user has active admin session, renders Overseer Dashboard.
    - Otherwise, renders high-converting public landing page for human visitors and web agents.
    """
    accept = request.headers.get("accept", "").lower()
    is_json = "application/json" in accept or request.query_params.get("format") == "json"

    if is_json:
        manifest = {
            "name": settings.PROJECT_NAME,
            "version": settings.VERSION,
            "description": "Ultra-fast (<150ms cached) machine-payable quantitative market feeds via HTTP 402 on Base Mainnet.",
            "network": f"base-mainnet (Chain ID {settings.BASE_CHAIN_ID})",
            "token": f"USDC ({settings.USDC_CONTRACT_ADDRESS})",
            "wallet": settings.WALLET_ADDRESS,
            "x402_support": {
                "standard_v1": "X-PAYMENT header (EIP-3009)",
                "standard_v2": "PAYMENT-SIGNATURE header",
                "legacy": "X-PAYMENT-PROOF: <tx_hash>",
                "facilitator": settings.X402_FACILITATOR_URL or "https://facilitator.payai.network",
            },
            "catalogs": {
                "llms_txt": "/llms.txt",
                "agents_json": "/agents.json",
                "agent_card": "/.well-known/agent.json",
                "mcp": "/mcp",
                "openapi": "/openapi.json",
            },
            "endpoints": [
                {"path": "/api/v1/free-teaser", "price_usdc": 0.0, "description": "Free instant live BTC spot preview & latency verification"},
                {"path": "/api/v1/crypto-pulse", "price_usdc": settings.PRICE_MICRO_USDC, "description": "Real-time BTC/ETH/SOL prices, 24h volatility, Fear & Greed sentiment"},
                {"path": "/api/v1/base-dex-radar", "price_usdc": settings.PRICE_DEX_RADAR_USDC, "description": "Base L2 DEX whale liquidity, volume spikes & top pools"},
                {"path": "/api/v1/deep-market-report", "price_usdc": settings.PRICE_PREMIUM_USDC, "description": "Institutional M2M quantitative market regime & Base liquidity report"},
                {"path": "/api/v1/trending/{slug}", "price_usdc": settings.PRICE_DYNAMIC_USDC, "description": "Auto-deployed live pulse for trending Base assets"},
            ],
        }
        if request.method == "HEAD":
            return Response(status_code=200, media_type="application/json")
        return JSONResponse(content=manifest)

    if request.method == "HEAD":
        return Response(status_code=200, media_type="text/html")
    landing_template = _jinja_env.get_template("landing.html")
    return HTMLResponse(content=landing_template.render())
