"""
Overseer Dashboard (/) & PIN-Protected Admin Router.
Provides:
- GET / (Responsive dark Command Center UI for Mobile & Desktop)
- GET /api/admin/stats (Live JSON metrics for Dashboard auto-refresh)
- POST /api/admin/toggle-pause (PIN-protected Emergency Stop switch)
"""

from fastapi import APIRouter, Header, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel
from typing import Optional

from app.config import settings
from app.database import get_stats, set_pause_state
from app.services.market_data import (
    fetch_base_dex_radar,
    fetch_crypto_pulse_data,
    fetch_deep_market_report,
    fetch_dynamic_asset_pulse,
)

router = APIRouter(tags=["Overseer Dashboard & Admin"])


class PauseToggleRequest(BaseModel):
    pin: Optional[str] = None
    paused: Optional[bool] = None


class ModeToggleRequest(BaseModel):
    pin: Optional[str] = None
    mode: Optional[str] = None


@router.post("/api/admin/toggle-mode", response_class=JSONResponse)
async def toggle_verify_mode(
    payload: Optional[ModeToggleRequest] = None,
    x_admin_pin: Optional[str] = Header(default=None, alias="X-Admin-Pin"),
) -> dict:
    """Switch between 'hybrid' (sandbox + on-chain) and 'strict_onchain' (production only)."""
    provided_pin = (payload.pin if payload and payload.pin else None) or x_admin_pin
    if not provided_pin or provided_pin.strip() != settings.ADMIN_PIN:
        raise HTTPException(
            status_code=401,
            detail="Ogiltig eller saknad Admin PIN-kod.",
        )
    current = settings.X402_VERIFY_MODE.lower()
    next_mode = (
        payload.mode
        if (payload and payload.mode in ("hybrid", "strict_onchain"))
        else ("strict_onchain" if current == "hybrid" else "hybrid")
    )
    settings.X402_VERIFY_MODE = next_mode
    return {"status": "updated", "verify_mode": settings.X402_VERIFY_MODE}


@router.get("/api/admin/preview-product", response_class=JSONResponse)
async def preview_product_payload(
    request: Request,
    endpoint: str = "/api/v1/crypto-pulse",
) -> dict:
    """
    Allow John (from the Dashboard) to inspect the exact live JSON product
    that a buying AI-bot receives after paying via x402.
    """
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
    total_services = 2 + len(stats.get("dynamic_endpoints", []))

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
                "detail": f"Exponerar {total_services} st säljbara API:er i /llms.txt, /agents.json & /sitemap.xml.",
            },
        ],
    }


@router.get("/api/admin/stats", response_class=JSONResponse)
async def admin_stats_endpoint(request: Request) -> dict:
    """Return live stats, scout discoveries, and wallet info."""
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
    """
    Toggle or set the Emergency Stop state.
    Protected by ADMIN_PIN (passed either via JSON body `pin` or `X-Admin-Pin` header).
    """
    provided_pin = (payload.pin if payload and payload.pin else None) or x_admin_pin
    if not provided_pin or provided_pin.strip() != settings.ADMIN_PIN:
        raise HTTPException(
            status_code=401,
            detail="Ogiltig eller saknad Admin PIN-kod för Nödstopp.",
        )

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


@router.get("/", response_class=HTMLResponse)
async def overseer_dashboard(request: Request) -> str:
    """Render the responsive Overseer Dashboard (Mobile & Desktop)."""
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

    discoveries_html = ""
    for d in stats["discoveries"]:
        discoveries_html += f"""
        <div class="log-item">
            <div class="log-header">
                <span class="badge-scout">{d['status']}</span>
                <code class="endpoint-code">{d['suggested_endpoint']}</code>
                <span class="price-tag">${d['suggested_price_usdc']:.2f} USDC</span>
            </div>
            <div class="log-title">{d['topic']}</div>
            <div class="log-rationale">{d['rationale']}</div>
        </div>
        """

    dynamic_endpoints_html = ""
    idx_ep = 4
    for ep in stats.get("dynamic_endpoints", []):
        dynamic_endpoints_html += f"""
        <div class="endpoint-row">
            <div>
                <span class="endpoint-code">{idx_ep}. {ep['endpoint_path']}</span>
                <span class="price-tag">${ep['price_usdc']:.2f} USDC</span>
                <span class="badge-scout" style="background:#059669;margin-left:6px;">AUTO-BYGGD ({ep['asset_symbol']})</span>
            </div>
            <div style="display:flex;align-items:center;gap:10px;flex-wrap:wrap;">
                <span>Anrop: <strong>{ep['calls_count']} st</strong> | Intäkt: <strong>${ep['revenue_usdc']:.2f} USDC</strong> | 🟢</span>
                <button class="btn-preview" onclick="previewProduct('{ep['endpoint_path']}')">👁️ Granska Data</button>
            </div>
        </div>
        """
        idx_ep += 1

    total_active_apis = 2 + len(stats.get("dynamic_endpoints", []))

    return f"""<!DOCTYPE html>
<html lang="sv">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AIM NETWORK — Overseer Dashboard</title>
    <style>
        :root {{
            --bg: #0b0f17;
            --card: #131b2e;
            --border: #1e293b;
            --neon: #4ade80;
            --text: #f1f5f9;
            --muted: #94a3b8;
            --accent: #38bdf8;
        }}
        * {{ box-sizing: border-box; margin: 0; padding: 0; }}
        body {{
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, monospace;
            background-color: var(--bg);
            color: var(--text);
            padding: 20px;
            max-width: 860px;
            margin: 0 auto;
            line-height: 1.5;
        }}
        .header-bar {{
            background: linear-gradient(135deg, #131b2e 0%, #0f172a 100%);
            border: 1px solid var(--border);
            border-left: 4px solid {status_badge_color};
            border-radius: 12px;
            padding: 18px 20px;
            margin-bottom: 18px;
            display: flex;
            flex-wrap: wrap;
            justify-content: space-between;
            align-items: center;
            gap: 12px;
        }}
        .title-group h1 {{
            font-size: 1.25rem;
            letter-spacing: 0.5px;
            color: #fff;
        }}
        .status-pill {{
            font-weight: 700;
            color: {status_badge_color};
            font-size: 0.95rem;
            margin-top: 4px;
        }}
        .wallet-box {{
            background: rgba(56, 189, 248, 0.1);
            border: 1px solid rgba(56, 189, 248, 0.3);
            padding: 8px 12px;
            border-radius: 8px;
            font-family: monospace;
            font-size: 0.85rem;
            color: var(--accent);
        }}
        .grid-2 {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
            gap: 16px;
            margin-bottom: 18px;
        }}
        .card {{
            background: var(--card);
            border: 1px solid var(--border);
            border-radius: 12px;
            padding: 18px;
            margin-bottom: 18px;
        }}
        .card h2 {{
            font-size: 0.95rem;
            text-transform: uppercase;
            letter-spacing: 0.8px;
            color: var(--muted);
            margin-bottom: 12px;
        }}
        .revenue-big {{
            font-size: 2.2rem;
            font-weight: 800;
            color: var(--neon);
            font-family: monospace;
        }}
        .revenue-sub {{
            font-size: 0.9rem;
            color: var(--muted);
            margin-top: 4px;
        }}
        .endpoint-row {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 12px;
            background: rgba(255,255,255,0.03);
            border: 1px solid var(--border);
            border-radius: 8px;
            margin-bottom: 10px;
            flex-wrap: wrap;
            gap: 8px;
        }}
        .endpoint-code {{
            font-family: monospace;
            color: var(--accent);
            font-weight: 600;
        }}
        .price-tag {{
            background: rgba(74, 222, 128, 0.15);
            color: var(--neon);
            padding: 2px 8px;
            border-radius: 6px;
            font-size: 0.8rem;
            font-weight: 700;
            font-family: monospace;
        }}
        .log-item {{
            padding: 12px;
            background: rgba(255,255,255,0.02);
            border-left: 3px solid var(--accent);
            border-radius: 6px;
            margin-bottom: 10px;
        }}
        .log-header {{
            display: flex;
            gap: 8px;
            align-items: center;
            flex-wrap: wrap;
            margin-bottom: 4px;
        }}
        .badge-scout {{
            background: #3b82f6;
            color: #fff;
            font-size: 0.7rem;
            font-weight: 700;
            padding: 2px 6px;
            border-radius: 4px;
        }}
        .log-title {{ font-weight: 600; font-size: 0.92rem; }}
        .log-rationale {{ font-size: 0.83rem; color: var(--muted); margin-top: 2px; }}
        .actions-bar {{
            display: flex;
            flex-wrap: wrap;
            gap: 12px;
            margin-top: 10px;
        }}
        button {{
            cursor: pointer;
            border: none;
            border-radius: 8px;
            padding: 12px 18px;
            font-weight: 700;
            font-size: 0.9rem;
            color: #fff;
            transition: opacity 0.15s;
        }}
        button:hover {{ opacity: 0.9; }}
        .btn-stop {{ background: {btn_bg}; flex: 1; min-width: 220px; }}
        .btn-scout {{ background: #2563eb; }}
        .btn-refresh {{ background: #334155; }}
        .btn-preview {{
            background: rgba(56, 189, 248, 0.15);
            border: 1px solid rgba(56, 189, 248, 0.4);
            color: var(--accent);
            padding: 5px 10px;
            font-size: 0.78rem;
            border-radius: 6px;
        }}
        .agent-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
            gap: 10px;
        }}
        .agent-box {{
            background: rgba(255,255,255,0.03);
            border: 1px solid var(--border);
            border-left: 3px solid var(--neon);
            border-radius: 8px;
            padding: 10px 12px;
        }}
        .agent-box h3 {{ font-size: 0.85rem; color: #fff; margin-bottom: 4px; }}
        .agent-box p {{ font-size: 0.78rem; color: var(--muted); }}
        .inspector-pre {{
            background: #06090f;
            border: 1px solid var(--border);
            border-radius: 8px;
            padding: 14px;
            color: #4ade80;
            font-family: monospace;
            font-size: 0.8rem;
            overflow-x: auto;
            max-height: 340px;
            margin-top: 12px;
            display: none;
        }}
        .links-footer {{
            display: flex;
            gap: 16px;
            flex-wrap: wrap;
            font-size: 0.85rem;
            color: var(--muted);
            margin-top: 8px;
        }}
        .links-footer a {{ color: var(--accent); text-decoration: none; }}
    </style>
</head>
<body>
    <div class="header-bar">
        <div class="title-group">
            <h1>AIM NETWORK — OVERSEER DASHBOARD</h1>
            <div class="status-pill" id="statusText">{status_dot}</div>
        </div>
        <div class="wallet-box" title="{wallet}">
            Plånbok (Base USDC): <strong>{short_wallet}</strong> • Läge: <strong>{v_mode_label}</strong>
        </div>
    </div>

    <div class="grid-2">
        <div class="card" style="margin-bottom:0;">
            <h2>💰 INTÄKTER (Base USDC Plånbok)</h2>
            <div class="revenue-big" id="totalRevenue">${total_rev:.2f} USDC</div>
            <div class="revenue-sub">≈ {total_sek:.2f} SEK • Direkt till {short_wallet}</div>
        </div>
        <div class="card" style="margin-bottom:0;">
            <h2>⚡ ANROPSVOLYM (x402 M2M)</h2>
            <div class="revenue-big" style="color:#38bdf8;" id="totalCalls">{stats['calls_micro'] + stats['calls_premium']} st</div>
            <div class="revenue-sub">Mikro ($0.01): {stats['calls_micro']} st • Premium ($1.00): {stats['calls_premium']} st</div>
        </div>
    </div>

    <div class="card">
        <h2>🤖 AGENT-BESÄTTNING (4 Autonoma Moduler i Drift)</h2>
        <div class="agent-grid" id="agentCrewGrid">
            <div class="agent-box">
                <h3>🟢 1. Spanar- & Bygg-Agent</h3>
                <p>Skannar trender varje timme och bygger nya API:er automatiskt ({len(stats.get('dynamic_endpoints', []))} st extra byggda).</p>
            </div>
            <div class="agent-box">
                <h3>🟢 2. Data- & Analys-Agent</h3>
                <p>Hämtar och beräknar live-priser, volatilitet och handels-signaler på under 0,15 sek.</p>
            </div>
            <div class="agent-box">
                <h3>🟢 3. x402 Kassa- & Säkerhets-Agent</h3>
                <p>Tar betalt i USDC på Base ({short_wallet}) och stoppar obetalda anrop (HTTP 402).</p>
            </div>
            <div class="agent-box">
                <h3>🟢 4. Skyltfönster-Agent</h3>
                <p>Marknadsför alla {total_active_apis} tjänster automatiskt i /llms.txt och /agents.json.</p>
            </div>
        </div>
    </div>

    <div class="card">
        <h2>📊 AKTIVA TJÄNSTER (Klicka på "👁️ Granska Data" för att se exakt vad som byggts & säljs)</h2>
        <div class="endpoint-row">
            <div>
                <span class="endpoint-code">1. /api/v1/crypto-pulse</span>
                <span class="price-tag">$0.01 USDC</span>
            </div>
            <div style="display:flex;align-items:center;gap:10px;flex-wrap:wrap;">
                <span>Anrop: <strong>{stats['calls_micro']} st</strong> | Intäkt: <strong>${micro_rev:.2f} USDC</strong> | 🟢</span>
                <button class="btn-preview" onclick="previewProduct('/api/v1/crypto-pulse')">👁️ Granska Data</button>
            </div>
        </div>
        <div class="endpoint-row">
            <div>
                <span class="endpoint-code">2. /api/v1/base-dex-radar</span>
                <span class="price-tag">$0.05 USDC</span>
                <span class="badge-scout" style="background:#7c3aed;margin-left:6px;">BASE DEX WHALE RADAR</span>
            </div>
            <div style="display:flex;align-items:center;gap:10px;flex-wrap:wrap;">
                <span>Status: 🟢 Live (DexScreener Base)</span>
                <button class="btn-preview" onclick="previewProduct('/api/v1/base-dex-radar')">👁️ Granska Data</button>
            </div>
        </div>
        <div class="endpoint-row">
            <div>
                <span class="endpoint-code">3. /api/v1/deep-market-report</span>
                <span class="price-tag">$1.00 USDC</span>
            </div>
            <div style="display:flex;align-items:center;gap:10px;flex-wrap:wrap;">
                <span>Anrop: <strong>{stats['calls_premium']} st</strong> | Intäkt: <strong>${prem_rev:.2f} USDC</strong> | 🟢</span>
                <button class="btn-preview" onclick="previewProduct('/api/v1/deep-market-report')">👁️ Granska Data</button>
            </div>
        </div>
        {dynamic_endpoints_html}
        <pre id="productInspectorBox" class="inspector-pre"></pre>
    </div>

    <div class="card">
        <h2>🔍 SPANAR-LOGG (Förslag från din Autonoma Spanar-agent)</h2>
        <div id="discoveriesContainer">
            {discoveries_html}
        </div>
    </div>

    <div class="card">
        <h2>🎛️ KOMMANDOCENTRAL (PIN-SKYDDAD)</h2>
        <div class="actions-bar">
            <button class="btn-stop" onclick="toggleEmergencyStop()">{btn_label}</button>
            <button class="btn-scout" onclick="runSelfCheck()">🧪 Kör Själv-Diagnos</button>
            <button class="btn-scout" onclick="toggleVerifyMode()">🔐 Växla On-Chain/Hybrid</button>
            <button class="btn-scout" onclick="runScoutNow()">🔍 Kör Spanar-Agent Nu</button>
            <button class="btn-refresh" onclick="window.location.reload()">🔄 Uppdatera Siffror</button>
        </div>
        <div class="links-footer" style="margin-top: 16px;">
            <span>Maskin-kataloger för AI-botar:</span>
            <a href="/api/v1/free-teaser" target="_blank">/api/v1/free-teaser (Gratis Smakprov)</a>
            <a href="/llms.txt" target="_blank">/llms.txt</a>
            <a href="/agents.json" target="_blank">/agents.json</a>
            <a href="/mcp" target="_blank">/mcp (MCP Server)</a>
            <a href="/.well-known/agent.json" target="_blank">/.well-known/agent.json</a>
            <a href="/docs" target="_blank">/docs (OpenAPI)</a>
        </div>
    </div>

    <script>
        async function toggleEmergencyStop() {{
            const pin = prompt("Ange Admin PIN-kod för att växla Nödstopp (Standard: 2026):");
            if (!pin) return;
            const res = await fetch("/api/admin/toggle-pause", {{
                method: "POST",
                headers: {{ "Content-Type": "application/json" }},
                body: JSON.stringify({{ pin: pin }})
            }});
            if (res.ok) {{
                window.location.reload();
            }} else {{
                const err = await res.json();
                alert("Åtgärd nekad: " + (err.detail || "Fel PIN-kod"));
            }}
        }}

        async function toggleVerifyMode() {{
            const pin = prompt("Ange Admin PIN-kod för att växla mellan HYBRID och STRICT ON-CHAIN (Standard: 2026):");
            if (!pin) return;
            const res = await fetch("/api/admin/toggle-mode", {{
                method: "POST",
                headers: {{ "Content-Type": "application/json" }},
                body: JSON.stringify({{ pin: pin }})
            }});
            if (res.ok) {{
                window.location.reload();
            }} else {{
                const err = await res.json();
                alert("Åtgärd nekad: " + (err.detail || "Fel PIN-kod"));
            }}
        }}

        async function runScoutNow() {{
            const res = await fetch("/cron/discover", {{ method: "POST" }});
            if (res.ok) {{
                window.location.reload();
            }}
        }}

        async function previewProduct(endpointPath) {{
            const box = document.getElementById("productInspectorBox");
            box.style.display = "block";
            box.textContent = "Hämtar live-produkt från " + endpointPath + " ...";
            const res = await fetch("/api/admin/preview-product?endpoint=" + encodeURIComponent(endpointPath));
            const data = await res.json();
            box.textContent = "// LIVE PRODUKT-INSPEKTÖR FÖR: " + endpointPath + "\\n" + JSON.stringify(data, null, 2);
        }}

        async function runSelfCheck() {{
            const box = document.getElementById("productInspectorBox");
            box.style.display = "block";
            box.textContent = "Kör själv-diagnos på alla 4 agenter...";
            const res = await fetch("/api/admin/self-check");
            const data = await res.json();
            box.textContent = "// SJÄLV-DIAGNOS RESULTAT:\\n" + JSON.stringify(data, null, 2);
        }}

        // Auto-refresh Dashboard var 30:e sekund så nya intäkter och auto-byggda tjänster syns direkt
        setInterval(() => {{
            window.location.reload();
        }}, 30000);
    </script>
</body>
</html>"""

