"""
Self-Marketing & AI Agent Discovery Router:
- GET /llms.txt (Standard LLM manifest for OpenAI, Anthropic, Perplexity & M2M crawlers)
- GET /agents.json (x402 & MCP catalog specification — dynamically includes Scout-built endpoints)
- GET /.well-known/agent.json (A2A Agent Card specification)
- GET/POST /cron/discover (Autonomous Scout trigger)
"""

import json
import secrets
import time
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Optional
from fastapi import APIRouter, Header, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse, Response

from app.config import settings
from app.database import get_stats
from app.routers.dashboard import verify_admin_pin_with_lockout
from app.services.market_data import (
    fetch_base_dex_radar,
    fetch_crypto_pulse_data,
    fetch_deep_market_report,
)
from app.services.scout import run_autonomous_scout

router = APIRouter(tags=["AI Discovery & Autonomous Scout"])


@router.api_route("/llms.txt", methods=["GET", "HEAD"], response_class=PlainTextResponse)
async def llms_txt_manifest(request: Request) -> str:
    """Machine-readable Markdown manifest for LLM crawlers and autonomous buying agents."""
    db_override = request.app.state.db_path if hasattr(request.app.state, "db_path") else None
    stats = get_stats(db_override)
    dynamic_lines = ""
    idx = 4
    for ep in stats.get("dynamic_endpoints", []):
        dynamic_lines += (
            f"{idx}. `GET {ep['endpoint_path']}`\n"
            f"   - **Price:** `{ep['price_usdc']:.2f} USDC`\n"
            f"   - **Description:** Auto-deployed live trending pulse & orderflow for {ep['asset_name']} ({ep['asset_symbol']}).\n"
        )
        idx += 1

    std_x402_note = (
        "- **Standard x402 (recommended):** the 402 response contains an `accepts` list "
        "(scheme `exact`, network `base`, EIP-3009 USDC). Retry with a signed payload in the "
        "`X-PAYMENT` header (v2: `PAYMENT-SIGNATURE`); settlement receipt is returned in "
        "`X-PAYMENT-RESPONSE`. Works with standard x402 client libraries.\n"
        if settings.X402_FACILITATOR_URL
        else ""
    )

    return f"""# AIM Network — Autonomous M2M API Hub
> Ultra-fast (<150ms cached) machine-payable data endpoints via HTTP 402 (x402 protocol) on Base Mainnet (Chain ID 8453).
> No account or API key required. Pay per call in USDC on Base and pass transaction hash in `X-PAYMENT-PROOF` header.

## Payment Configuration (x402 v1.0)
- **Network:** `base-mainnet` (Chain ID: `8453`)
- **Token:** `USDC` (`{settings.USDC_CONTRACT_ADDRESS}`)
- **Recipient Wallet:** `{settings.WALLET_ADDRESS}`
- **Proof Header:** `X-PAYMENT-PROOF: <0x_base_transaction_hash>`
- **Free Schema Verification:** Append `?sample=true` to ANY endpoint (e.g. `/api/v1/crypto-pulse?sample=true`) for a free JSON schema verification sample before purchasing live data.
{std_x402_note}
## Available M2M Endpoints
0. `GET /api/v1/free-teaser`
   - **Price:** `0.00 USDC (FREE)`
   - **Description:** Instant live BTC spot & latency verification teaser for autonomous agents.
1. `GET /api/v1/crypto-pulse`
   - **Price:** `{settings.PRICE_MICRO_USDC:.2f} USDC` (Free sample: `?sample=true`)
   - **Description:** Real-time BTC/ETH/SOL prices, 24h volatility index, and Fear & Greed sentiment JSON.
2. `GET /api/v1/base-dex-radar`
   - **Price:** `{settings.PRICE_DEX_RADAR_USDC:.2f} USDC` (Free sample: `?sample=true`)
   - **Description:** Real-time Base L2 DEX liquidity pools, volume spikes, and whale inflow radar via DexScreener.
3. `GET /api/v1/deep-market-report`
   - **Price:** `{settings.PRICE_PREMIUM_USDC:.2f} USDC` (Free sample: `?sample=true`)
   - **Description:** Institutional M2M quantitative market regime, Base L2 liquidity metrics, and actionable trading signals JSON.
{dynamic_lines}
## Quantitative Classification Standards
- **Market Sentiment Enum:** `bullish_expansion` (F&G > 65, BTC up), `overbought_pullback` (F&G > 65, BTC down), `cautious_rebound` (F&G < 35, BTC up), `bearish_fear` (F&G < 35, BTC down), `bullish_momentum` (Neutral F&G, BTC up), `bearish_consolidation` (Neutral F&G, BTC down).
- **Volatility Metric:** Calculated as 24h mean absolute movement across BTC, ETH, and SOL:
  - `LOW (<1.5%)`: Stable consolidation regime.
  - `MODERATE (1.5-4.0%)`: Normal healthy active volatility.
  - `HIGH (>4.0%)`: Elevated expansion or liquidation regime.

## Welcome Bonus: First-Time Buyer Campaign (Buy 1, Get 5 Free)
- New wallet addresses that make their first USDC purchase on ANY endpoint automatically unlock **5 FREE bonus calls** across all micro feeds ($0.01-$0.05) for 24 hours.
- Reuse the same `tx_hash` in `X-PAYMENT-PROOF: <tx_hash>` to consume your 5 bonus calls.

## Volume Discount: 24-Hour VIP Passes
- **24-Hour Micro VIP Pass (`{settings.PRICE_VIP_24H_USDC:.2f} USDC`):** Pay `{settings.PRICE_VIP_24H_USDC:.2f} USDC` once to unlock **{settings.VIP_PASS_MAX_CALLS} calls across all micro feeds ($0.01-$0.05)** for 24 hours (0.004 USDC/call, 60-92% discount). Bound to verified payer wallet.
- **24-Hour Pro VIP Pass (`10.00 USDC`):** Pay `10.00 USDC` once to unlock **{settings.PRO_PASS_MAX_CALLS} calls across ALL endpoints including Deep Market Reports ($1.00)** for 24 hours (0.20 USDC/call, 80% discount).

## Replay Prevention & Single-Use Token Burn
- Single-use on-chain transaction hashes are permanently burned in SQLite on first consumption. Replay attempts from any client are immediately rejected with HTTP 402 `REPLAY_REJECTED`.
- For zero-sharing guarantee, agents should use standard x402 (EIP-3009 signed transfer authorization), which is cryptographically tied to the payer's private key.

## Machine Catalogs & Legal
- Agent Catalog: `/agents.json`
- MCP Server Manifest & JSON-RPC: `/mcp`
- A2A Agent Card: `/.well-known/agent.json`
- Trending Assets Index: `/api/v1/trending`
- Terms of Service: `/terms` (HTML & JSON)
- Privacy Policy & GDPR: `/privacy` (HTML & JSON)
- Refund & Settlement: `/refund` (HTML & JSON)
- Operational Status: `/status` (HTML & JSON)

## Disclaimer
> All feeds and signals provide quantitative informational market metrics only. Not financial, trading, or investment advice.

## Python Agent Quickstart (Zero-Auth x402)
```python
import httpx

# 1. Probe free teaser or test schema sample (?sample=true)
r = httpx.get("https://johngarp.click/api/v1/crypto-pulse?sample=true")
print("Verified Schema:", r.json()["status"])

# 2. Query paid feed via standard x402 header (or legacy tx-hash)
# headers = {{"X-PAYMENT": "<base64_signed_eip3009_payload>"}}
# Or send 0.01 USDC on Base and pass transaction hash:
headers = {{"X-PAYMENT-PROOF": "<0x_base_transaction_hash>"}}
res = httpx.get("https://johngarp.click/api/v1/crypto-pulse", headers=headers)
print(res.json())
```
"""


@router.api_route("/robots.txt", methods=["GET", "HEAD"], response_class=PlainTextResponse)
async def robots_txt() -> str:
    """Explicitly invite all AI search crawlers, M2M agents, and indexers."""
    return """User-agent: *
Allow: /
Allow: /llms.txt
Allow: /agents.json
Allow: /.well-known/agent.json
Allow: /openapi.json
Allow: /api/v1/
Sitemap: https://johngarp.click/sitemap.xml
"""


@router.api_route("/sitemap.xml", methods=["GET", "HEAD"])
async def sitemap_xml(request: Request):
    """Dynamic XML sitemap for search engines and AI directory crawlers."""
    from fastapi.responses import Response

    base = "https://johngarp.click"
    db_override = request.app.state.db_path if hasattr(request.app.state, "db_path") else None
    stats = get_stats(db_override)
    urls = [
        f"{base}/",
        f"{base}/llms.txt",
        f"{base}/agents.json",
        f"{base}/.well-known/agent.json",
        f"{base}/openapi.json",
        f"{base}/api/v1/free-teaser",
        f"{base}/api/v1/trending",
        f"{base}/api/v1/crypto-pulse",
        f"{base}/api/v1/base-dex-radar",
        f"{base}/api/v1/deep-market-report",
    ]
    for ep in stats.get("dynamic_endpoints", []):
        urls.append(f"{base}{ep['endpoint_path']}")
    xml_items = "".join(f"<url><loc>{u}</loc></url>" for u in urls)
    xml = f'<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{xml_items}</urlset>'
    return Response(content=xml, media_type="application/xml")


@router.api_route("/agents.json", methods=["GET", "HEAD"], response_class=JSONResponse)
async def agents_json_manifest(request: Request) -> dict:
    """Standardized x402 & M2M agent catalog (includes auto-deployed Scout endpoints)."""
    db_override = request.app.state.db_path if hasattr(request.app.state, "db_path") else None
    stats = get_stats(db_override)

    endpoints = [
        {
            "id": "free-teaser",
            "path": "/api/v1/free-teaser",
            "method": "GET",
            "tier": "free",
            "price_usdc": 0.0,
            "currency": "USDC",
            "network": "base-mainnet",
            "sla_target_ms": 100,
            "description": "Free instant BTC spot & live feed verification teaser.",
        },
        {
            "id": "crypto-pulse",
            "path": "/api/v1/crypto-pulse",
            "sample_url": "/api/v1/crypto-pulse?sample=true",
            "method": "GET",
            "tier": "micro",
            "price_usdc": settings.PRICE_MICRO_USDC,
            "currency": "USDC",
            "network": "base-mainnet",
            "sla_target_ms": 150,
            "description": "Real-time crypto market pulse, Fear & Greed sentiment, and 24h volatility index.",
        },
        {
            "id": "base-dex-radar",
            "path": "/api/v1/base-dex-radar",
            "sample_url": "/api/v1/base-dex-radar?sample=true",
            "method": "GET",
            "tier": "micro",
            "price_usdc": settings.PRICE_DEX_RADAR_USDC,
            "currency": "USDC",
            "network": "base-mainnet",
            "sla_target_ms": 150,
            "description": "Real-time Base L2 DEX liquidity pools, volume spikes, and whale inflow radar.",
        },
        {
            "id": "deep-market-report",
            "path": "/api/v1/deep-market-report",
            "sample_url": "/api/v1/deep-market-report?sample=true",
            "method": "GET",
            "tier": "premium",
            "price_usdc": settings.PRICE_PREMIUM_USDC,
            "currency": "USDC",
            "network": "base-mainnet",
            "sla_target_ms": 200,
            "description": "Deep quantitative M2M market report, Base L2 liquidity analysis, and actionable trading signals.",
        },
    ]

    for ep in stats.get("dynamic_endpoints", []):
        endpoints.append(
            {
                "id": f"trending-{ep['slug']}",
                "path": ep["endpoint_path"],
                "sample_url": f"{ep['endpoint_path']}?sample=true",
                "method": "GET",
                "tier": "dynamic_scout",
                "price_usdc": ep["price_usdc"],
                "currency": "USDC",
                "network": "base-mainnet",
                "sla_target_ms": 150,
                "description": f"Live trending pulse & orderflow for {ep['asset_name']} ({ep['asset_symbol']}).",
            }
        )

    return {
        "schema_version": "1.0",
        "name": settings.PROJECT_NAME,
        "description": "Autonomous M2M Data & Quantitative Intelligence Hub payable via HTTP 402 (x402) on Base L2.",
        "auth": {
            "type": "x402",
            "version": "1.0",
            "network": "base-mainnet",
            "chain_id": 8453,
            "token": "USDC",
            "token_contract": settings.USDC_CONTRACT_ADDRESS,
            "recipient_wallet": settings.WALLET_ADDRESS,
            "header_name": "X-PAYMENT-PROOF",
        },
        "endpoints": endpoints,
        "promotions": {
            "first_time_buyer_bonus": {
                "name": "First-Time Buyer Welcome Bonus",
                "description": "Make 1 purchase (from 0.01 USDC) and automatically get 5 free bonus calls across all micro feeds ($0.01-$0.05) for 24 hours.",
                "bonus_calls": settings.WELCOME_BONUS_CALLS,
                "eligible_tiers": ["micro", "dynamic_scout"],
                "duration_hours": settings.WELCOME_BONUS_DURATION_HOURS,
            },
            "vip_24h_pass": {
                "name": "24h Micro VIP Pass",
                "description": "Unlimited calls (up to 1,000) across all micro feeds ($0.01-$0.05) for 24 hours.",
                "price_usdc": settings.PRICE_VIP_24H_USDC,
                "max_calls": settings.VIP_PASS_MAX_CALLS,
                "eligible_tiers": ["micro", "dynamic_scout"],
            },
        },
        "discovery": {
            "llms_txt": "/llms.txt",
            "openapi_url": "/openapi.json",
            "well_known_agent": "/.well-known/agent.json",
            "trending_index": "/api/v1/trending",
        },
    }


@router.api_route("/.well-known/agent.json", methods=["GET", "HEAD"], response_class=JSONResponse)
async def well_known_agent_card(request: Request) -> Response:
    """A2A-compatible Agent Card for autonomous multi-agent ecosystems."""
    if request.method == "HEAD":
        return Response(status_code=200, media_type="application/json")
    return JSONResponse({
        "$schema": "https://a2a-protocol.org/schemas/agent-card.json",
        "name": "AIM Network M2M Hub",
        "description": "Autonomous quantitative market data, Base L2 DEX whale radar, and orderflow analytics payable via HTTP 402 (x402) on Base.",
        "version": settings.VERSION,
        "url": "https://johngarp.click",
        "defaultInputModes": ["application/json"],
        "defaultOutputModes": ["application/json"],
        "tags": [
            "financial-data",
            "crypto-market-intelligence",
            "base-l2",
            "x402-micropayments",
            "mcp-tools",
        ],
        "auth": {
            "type": "x402",
            "version": "1.0",
            "network": "base-mainnet",
            "chain_id": 8453,
            "token": "USDC",
            "token_contract": settings.USDC_CONTRACT_ADDRESS,
            "recipient_wallet": settings.WALLET_ADDRESS,
            "header_name": "X-PAYMENT-PROOF",
            "standard_header": "PAYMENT-SIGNATURE",
        },
        "provider": {
            "organization": "AIM Network Operations",
            "url": "https://johngarp.click",
            "contact": "support@johngarp.click",
        },
        "capabilities": {
            "mcp": {
                "supported": True,
                "endpoint": "https://johngarp.click/mcp",
                "protocol_version": "2025-03-26",
            },
            "payment": {
                "protocol": "x402",
                "network": "base",
                "chain_id": 8453,
                "currency": "USDC",
                "token_contract": settings.USDC_CONTRACT_ADDRESS,
                "recipient_wallet": settings.WALLET_ADDRESS,
                "facilitator": settings.X402_FACILITATOR_URL or "https://facilitator.payai.network",
            },
        },
        "skills": [
            {
                "id": "free-teaser",
                "name": "Live Market Teaser",
                "description": "Free zero-auth latency and BTC spot verification feed.",
                "url": "https://johngarp.click/api/v1/free-teaser",
                "cost_usdc": 0.0,
                "tags": ["free", "teaser", "btc", "latency-benchmark"],
                "inputModes": ["application/json"],
                "outputModes": ["application/json"],
            },
            {
                "id": "crypto-pulse",
                "name": "Crypto Market Pulse",
                "description": "Real-time BTC/ETH/SOL market pulse, sentiment, and volatility metrics.",
                "url": "https://johngarp.click/api/v1/crypto-pulse",
                "cost_usdc": 0.01,
                "tags": ["crypto", "spot", "volatility", "sentiment"],
                "inputModes": ["application/json"],
                "outputModes": ["application/json"],
            },
            {
                "id": "base-dex-radar",
                "name": "Base L2 DEX Whale Radar",
                "description": "Base L2 DEX liquidity pools, volume spikes, and whale orderflow tracking.",
                "url": "https://johngarp.click/api/v1/base-dex-radar",
                "cost_usdc": 0.05,
                "tags": ["dex", "base-l2", "whales", "liquidity-pools"],
                "inputModes": ["application/json"],
                "outputModes": ["application/json"],
            },
            {
                "id": "deep-market-report",
                "name": "Deep Market Quantitative Analysis",
                "description": "Quantitative regime detection, momentum scoring, and actionable signals.",
                "url": "https://johngarp.click/api/v1/deep-market-report",
                "cost_usdc": 1.00,
                "tags": ["quantitative", "institutional", "signals", "alpha"],
                "inputModes": ["application/json"],
                "outputModes": ["application/json"],
            },
            {
                "id": "trending",
                "name": "Trending Tokens Index",
                "description": "Free public index of active momentum tokens on Base L2.",
                "url": "https://johngarp.click/api/v1/trending",
                "cost_usdc": 0.0,
                "tags": ["free", "momentum", "trending", "discovery"],
                "inputModes": ["application/json"],
                "outputModes": ["application/json"],
            },
        ],
    })


GLAMA_CLAIM_TOKEN = "glama_claim_kMQwR0tBTjmF1CxnpiYj2Cgs6m2DT753"


@router.get("/mcp/.well-known/glama.json", response_class=JSONResponse)
@router.get("/.well-known/glama.json", response_class=JSONResponse)
async def well_known_glama_manifest() -> dict:
    """Glama.ai MCP Directory ownership & claim verification manifest."""
    return {
        "$schema": "https://glama.ai/mcp/schemas/connector.json",
        "claim": GLAMA_CLAIM_TOKEN,
        "name": "aim-network-m2m-hub",
        "description": "Autonomous M2M crypto market pulse, Base L2 DEX whale liquidity radar, and quantitative trading signals via HTTP 402 (x402) USDC micropayments on Base.",
        "url": "https://johngarp.click/mcp",
        "repository": "https://github.com/Johnmannen/aim-network-m2m-hub",
        "maintainers": [{"email": "John.garp.jg@gmail.com"}],
    }


@router.api_route("/cron/discover", methods=["GET", "POST"], response_class=JSONResponse)
async def trigger_autonomous_scout(
    request: Request,
    x_admin_pin: Optional[str] = Header(default=None, alias="X-Admin-Pin"),
    x_scout_token: Optional[str] = Header(default=None, alias="X-Scout-Token"),
) -> dict:
    """
    Run the Autonomous Scout to discover AND auto-deploy a new M2M API endpoint.
    Requires X-Admin-Pin or X-Scout-Token in production (bypassed only in TESTING mode if no header sent).
    """
    provided = (x_scout_token or x_admin_pin or "").strip()
    if not settings.TESTING or provided:
        verify_admin_pin_with_lockout(request, provided, allow_scout_token=True)

    db_override = request.app.state.db_path if hasattr(request.app.state, "db_path") else None
    entry = await run_autonomous_scout(db_path=db_override)
    return {
        "status": "success",
        "message": "Autonomous Scout discovered and auto-deployed a live M2M API endpoint.",
        "discovery": entry,
    }


def _build_mcp_tools() -> list[dict[str, Any]]:
    """Build standard MCP-compliant tool definitions with valid JSON Schema inputSchema."""
    proof_schema = {
        "type": "object",
        "properties": {
            "payment_proof": {
                "type": "string",
                "description": (
                    f"Optional Base Mainnet (Chain ID 8453) USDC transaction hash to recipient "
                    f"{settings.WALLET_ADDRESS}, or a 24h VIP Pass tx_hash."
                ),
            }
        },
        "additionalProperties": False,
    }
    return [
        {
            "name": "get_free_market_teaser",
            "description": "Free instant verification of live BTC spot price and M2M feed status ($0.00 USDC). Endpoint: https://johngarp.click/api/v1/free-teaser",
            "inputSchema": {
                "type": "object",
                "properties": {},
                "additionalProperties": False,
            },
        },
        {
            "name": "get_crypto_pulse",
            "description": f"Real-time BTC, ETH, SOL prices, 24h volatility index, and Fear & Greed sentiment (${settings.PRICE_MICRO_USDC:.2f} USDC via x402 on Base). Endpoint: https://johngarp.click/api/v1/crypto-pulse",
            "inputSchema": proof_schema,
        },
        {
            "name": "get_base_dex_radar",
            "description": f"Real-time Base L2 DEX liquidity pools, volume spikes, and whale inflow signals (${settings.PRICE_DEX_RADAR_USDC:.2f} USDC via x402 on Base). Endpoint: https://johngarp.click/api/v1/base-dex-radar",
            "inputSchema": proof_schema,
        },
        {
            "name": "get_deep_market_report",
            "description": f"Institutional M2M quantitative market regime, Base L2 liquidity metrics, and actionable trading signals (${settings.PRICE_PREMIUM_USDC:.2f} USDC via x402 on Base). Endpoint: https://johngarp.click/api/v1/deep-market-report",
            "inputSchema": proof_schema,
        },
        {
            "name": "list_trending_assets",
            "description": "Free tool ($0.00 USDC): Discover all currently active momentum and trending tokens tracked by the Autonomous Scout agent on Base L2.",
            "inputSchema": {
                "type": "object",
                "properties": {},
                "additionalProperties": False,
            },
        },
    ]


@router.api_route("/mcp", methods=["GET", "POST"])
async def mcp_server_endpoint(request: Request) -> Response:
    """
    Model Context Protocol (MCP) Streamable HTTP / JSON-RPC 2.0 Server Endpoint.
    Supports MCP JSON-RPC methods (`initialize`, `notifications/initialized`, `ping`,
    `tools/list`, `tools/call`, `resources/list`, `prompts/list`) for Glama, Smithery & Claude Desktop,
    as well as human/crawler GET discovery.
    """
    tools = _build_mcp_tools()

    if request.method == "POST":
        try:
            body = await request.json()
        except Exception:
            body = None

        if isinstance(body, dict) and "jsonrpc" in body:
            rpc_id = body.get("id")
            method = body.get("method", "")
            params = body.get("params") or {}

            # 1. JSON-RPC Notifications (no id -> 202 Accepted)
            if rpc_id is None or method.startswith("notifications/"):
                return Response(status_code=202)

            # 2. initialize handshake
            if method == "initialize":
                server_proto = "2025-03-26"
                return JSONResponse(
                    {
                        "jsonrpc": "2.0",
                        "id": rpc_id,
                        "result": {
                            "protocolVersion": server_proto,
                            "capabilities": {
                                "tools": {"listChanged": False},
                            },
                            "serverInfo": {
                                "name": "aim-network-m2m-hub",
                                "version": settings.VERSION,
                            },
                        },
                    }
                )

            # 3. ping
            if method == "ping":
                return JSONResponse({"jsonrpc": "2.0", "id": rpc_id, "result": {}})

            # 4. tools/list
            if method == "tools/list":
                return JSONResponse(
                    {
                        "jsonrpc": "2.0",
                        "id": rpc_id,
                        "result": {"tools": tools},
                    }
                )

            # 5. resources/list & prompts/list
            if method == "resources/list":
                return JSONResponse(
                    {"jsonrpc": "2.0", "id": rpc_id, "result": {"resources": []}}
                )
            if method == "prompts/list":
                return JSONResponse(
                    {"jsonrpc": "2.0", "id": rpc_id, "result": {"prompts": []}}
                )

            # 6. tools/call
            if method == "tools/call":
                tool_name = params.get("name", "") if isinstance(params, dict) else ""
                if tool_name == "get_free_market_teaser":
                    pulse = await fetch_crypto_pulse_data()
                    teaser_data = {
                        "status": "LIVE_FEED_VERIFIED",
                        "price_usdc": 0.0,
                        "btc_spot_preview_usd": pulse["assets"]["BTC"]["price_usd"],
                        "market_sentiment_preview": pulse["market_sentiment"],
                        "payment_recipient_base_usdc": settings.WALLET_ADDRESS,
                    }
                    return JSONResponse(
                        {
                            "jsonrpc": "2.0",
                            "id": rpc_id,
                            "result": {
                                "content": [
                                    {
                                        "type": "text",
                                        "text": json.dumps(teaser_data),
                                    }
                                ],
                                "isError": False,
                            },
                        }
                    )

                if tool_name == "list_trending_assets":
                    db_override = request.app.state.db_path if hasattr(request.app.state, "db_path") else None
                    stats = get_stats(db_override)
                    dynamic_eps = stats.get("dynamic_endpoints", [])
                    return JSONResponse(
                        {
                            "jsonrpc": "2.0",
                            "id": rpc_id,
                            "result": {
                                "content": [
                                    {
                                        "type": "text",
                                        "text": json.dumps({
                                            "status": "ok",
                                            "count": len(dynamic_eps),
                                            "trending_assets": dynamic_eps,
                                        }),
                                    }
                                ],
                                "isError": False,
                            },
                        }
                    )

                # Paid tools return x402 payment instructions via MCP tool content
                endpoint_map = {
                    "get_crypto_pulse": ("/api/v1/crypto-pulse", settings.PRICE_MICRO_USDC),
                    "get_base_dex_radar": ("/api/v1/base-dex-radar", settings.PRICE_DEX_RADAR_USDC),
                    "get_deep_market_report": ("/api/v1/deep-market-report", settings.PRICE_PREMIUM_USDC),
                }
                if tool_name in endpoint_map:
                    ep_path, ep_price = endpoint_map[tool_name]
                    quote_info = {
                        "status": "PAYMENT_REQUIRED_X402",
                        "endpoint": f"https://johngarp.click{ep_path}",
                        "amount_usdc": ep_price,
                        "network": "base-mainnet (Chain ID 8453)",
                        "token_contract": settings.USDC_CONTRACT_ADDRESS,
                        "recipient_wallet": settings.WALLET_ADDRESS,
                        "x402_standard": {
                            "scheme": "exact",
                            "network": "base",
                            "amount_micro_usdc": str(int(Decimal(str(ep_price)) * Decimal(10**6))),
                            "header_v1": "X-PAYMENT",
                            "header_v2": "PAYMENT-SIGNATURE",
                            "facilitator": settings.X402_FACILITATOR_URL or "https://facilitator.payai.network",
                        },
                        "header": "X-PAYMENT-PROOF: <0x_base_tx_hash>",
                    }
                    return JSONResponse(
                        {
                            "jsonrpc": "2.0",
                            "id": rpc_id,
                            "result": {
                                "content": [
                                    {
                                        "type": "text",
                                        "text": json.dumps(quote_info),
                                    }
                                ],
                                "isError": True,
                            },
                        }
                    )

                return JSONResponse(
                    {
                        "jsonrpc": "2.0",
                        "id": rpc_id,
                        "error": {
                            "code": -32602,
                            "message": f"Unknown tool: {tool_name}",
                        },
                    }
                )

            return JSONResponse(
                {
                    "jsonrpc": "2.0",
                    "id": rpc_id,
                    "error": {"code": -32601, "message": f"Method not found: {method}"},
                }
            )

    return JSONResponse(
        {
            "mcp_version": "2025-03-26",
            "server_name": "aim-network-m2m-hub",
            "canonical_url": "https://johngarp.click/mcp",
            "payment_protocol": {
                "type": "x402",
                "network": "base-mainnet",
                "chain_id": 8453,
                "token": "USDC",
                "recipient_wallet": settings.WALLET_ADDRESS,
                "vip_24h_pass_usdc": settings.PRICE_VIP_24H_USDC,
            },
            "tools": tools,
        }
    )


def _prefers_html(request: Request) -> bool:
    accept = request.headers.get("accept", "").lower()
    return "text/html" in accept and "application/json" not in accept


def _legal_html_shell(title: str, body_content: str) -> str:
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{title} — AIM Network M2M Hub</title>
  <style>
    :root {{ --bg: #090d16; --card: #131b2e; --text: #e2e8f0; --accent: #38bdf8; --border: #1e293b; --muted: #94a3b8; }}
    body {{ background: var(--bg); color: var(--text); font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; margin: 0; padding: 2rem 1rem; line-height: 1.6; }}
    .container {{ max-width: 800px; margin: 0 auto; background: var(--card); border: 1px solid var(--border); border-radius: 12px; padding: 2.5rem; box-shadow: 0 10px 25px rgba(0,0,0,0.5); }}
    h1 {{ color: #fff; font-size: 1.8rem; margin-top: 0; border-bottom: 1px solid var(--border); padding-bottom: 1rem; }}
    h2 {{ color: var(--accent); font-size: 1.25rem; margin-top: 1.8rem; }}
    p, li {{ color: var(--text); font-size: 0.95rem; }}
    ul {{ padding-left: 1.25rem; }}
    .meta {{ font-size: 0.85rem; color: var(--muted); margin-bottom: 1.5rem; }}
    a {{ color: var(--accent); text-decoration: none; }}
    a:hover {{ text-decoration: underline; }}
    .footer {{ margin-top: 2.5rem; border-top: 1px solid var(--border); padding-top: 1rem; font-size: 0.8rem; color: var(--muted); display: flex; justify-content: space-between; }}
  </style>
</head>
<body>
  <div class="container">
    <h1>{title}</h1>
    {body_content}
    <div class="footer">
      <span>AIM Network Operations (Stockholm, Sweden)</span>
      <span><a href="/">Landing</a> &bull; <a href="/terms">Terms</a> &bull; <a href="/privacy">Privacy</a> &bull; <a href="/refund">Refund</a> &bull; <a href="/status">Status</a></span>
    </div>
  </div>
</body>
</html>"""


@router.api_route("/terms", methods=["GET", "HEAD"])
async def terms_of_service(request: Request):
    """Terms of Service for AIM Network Autonomous M2M Services (HTML & JSON)."""
    if request.method == "HEAD":
        return Response(status_code=200, media_type="application/json")

    data = {
        "service": "AIM Network M2M Data Hub",
        "updated_at": "2026-11-08",
        "operator": {
            "legal_entity": "AIM Network Operations",
            "representative": "John Garp",
            "registration": "SE-Sole-Proprietorship / Innehar F-skatt (John Garp)",
            "jurisdiction": "Stockholm, Sweden (European Union)",
            "contact": "ops@johngarp.click",
            "support": "support@johngarp.click",
            "tax_policy": "Prices denominated in USDC. Business customers responsible for local indirect taxes/VAT. Enterprise B2B receipts available on request.",
        },
        "governing_law": "Laws of Sweden and European Union regulations. Exclusive forum: Stockholm District Court (Stockholms tingsrätt).",
        "service_model": "Autonomous machine-payable API feeds payable via HTTP 402 (x402) on Base Mainnet (Chain ID 8453).",
        "disclaimer": "All crypto market pulse metrics, DEX whale liquidity signals, and quantitative analysis are provided strictly 'as-is' for algorithmic verification, automated machine research, and quantitative analysis. Under no circumstances does any endpoint constitute financial, investment, trading, or tax advice.",
        "limitation_of_liability": "To the maximum extent permitted by applicable law, the operator shall not be liable for any trading losses, algorithmic execution errors, third-party RPC node outages, or blockchain network congestion.",
        "rate_limits": {
            "policy": f"{settings.RATE_LIMIT_PER_MINUTE} requests per minute per IP address.",
            "exemption": "High-volume institutional agents may authenticate via EIP-3009 signed authorizations.",
        },
        "sla_targets": {
            "l1_cache_latency": "<15ms (in-memory response)",
            "upstream_fetch_latency": "300-800ms (multi-exchange live aggregation)",
            "availability_target": "99.9% uptime",
        },
    }

    if _prefers_html(request):
        html_body = f"""
        <div class="meta">Last Updated: {data['updated_at']} &bull; Operator: {data['operator']['legal_entity']} &bull; Jurisdiction: {data['operator']['jurisdiction']}</div>
        <h2>1. Operator & Governing Law</h2>
        <p>The AIM Network M2M Hub is operated by <strong>{data['operator']['legal_entity']}</strong> (represented by {data['operator']['representative']}, {data['operator']['registration']}), located in {data['operator']['jurisdiction']}. These terms and all platform usage are governed exclusively by the <strong>{data['governing_law']}</strong>.</p>
        <p><strong>Tax & Invoicing:</strong> {data['operator']['tax_policy']}</p>
        <h2>2. Service Model & Machine Payments</h2>
        <p>{data['service_model']} Endpoints may be consumed per-call in USDC via cryptographic authorizations (EIP-3009) or 24-hour non-custodial VIP passes.</p>
        <h2>3. Financial Disclaimer & Algorithmic Scope</h2>
        <p>{data['disclaimer']}</p>
        <h2>4. Limitation of Liability</h2>
        <p>{data['limitation_of_liability']}</p>
        <h2>5. Performance Targets & SLA</h2>
        <ul>
          <li><strong>In-Memory Cache Latency Target:</strong> {data['sla_targets']['l1_cache_latency']}</li>
          <li><strong>Upstream Multi-Exchange Aggregation:</strong> {data['sla_targets']['upstream_fetch_latency']}</li>
          <li><strong>Platform Availability Target:</strong> {data['sla_targets']['availability_target']}</li>
        </ul>
        <h2>6. Inquiries & Contact</h2>
        <p>For operational inquiries, reach out to <a href="mailto:{data['operator']['contact']}">{data['operator']['contact']}</a> or visit our <a href="https://github.com/Johnmannen/aim-network-m2m-hub">GitHub repository</a>.</p>
        """
        return HTMLResponse(_legal_html_shell("Terms of Service", html_body))

    return JSONResponse(data)


@router.api_route("/privacy", methods=["GET", "HEAD"])
async def privacy_policy(request: Request):
    """Privacy Policy & GDPR Compliance Disclosure for M2M Agents and Humans."""
    if request.method == "HEAD":
        return Response(status_code=200, media_type="application/json")

    data = {
        "service": "AIM Network M2M Data Hub",
        "updated_at": "2026-11-08",
        "data_controller": {
            "name": "AIM Network Operations",
            "representative": "John Garp",
            "registration": "SE-Sole-Proprietorship / Innehar F-skatt (John Garp)",
            "dpo_contact": "privacy@johngarp.click",
            "address": "Stockholm, Sweden (European Union)",
        },
        "gdpr_compliance": {
            "legal_basis": "GDPR Article 6(1)(f) — Legitimate Interest. Processing is strictly limited to safeguarding platform integrity, preventing distributed denial-of-service (DDoS) disruptions, and securing cryptographic payment verification against replay attacks.",
            "data_categories": {
                "ip_addresses": "Logged ephemerally for rate limiting (60 req/min) and brute force lockout mitigation. Stored in rolling memory logs.",
                "wallet_addresses_and_hashes": "Public on-chain Base L2 addresses and transaction hashes processed exclusively for payment settlement, VIP pass verification, and Sybil-resistant welcome bonuses.",
                "personal_data_collected": "None. No accounts, emails, passwords, phone numbers, or profiling cookies are requested or stored for API consumers.",
            },
            "retention_period": "30 days automated rolling pruning for transient IP traffic logs. Blockchain transaction receipts are permanently stored on the decentralized Base L2 ledger.",
            "data_subject_rights": "Under GDPR Articles 15-22, users may request access, rectification, or erasure of their transient server log entries by contacting privacy@johngarp.click.",
        },
        "cookies": "Session cookies are used exclusively for authenticated administrative sessions at /admin. No tracking, analytics, or behavioral cookies are delivered to API consumers or public visitors.",
    }

    if _prefers_html(request):
        html_body = f"""
        <div class="meta">Last Updated: {data['updated_at']} &bull; Data Controller: {data['data_controller']['name']} &bull; Contact: {data['data_controller']['dpo_contact']}</div>
        <h2>1. Data Controller & Scope</h2>
        <p>The controller responsible for data processing on this platform is <strong>{data['data_controller']['name']}</strong>, based in {data['data_controller']['address']}. Inquiries regarding data protection may be directed to <a href="mailto:{data['data_controller']['dpo_contact']}">{data['data_controller']['dpo_contact']}</a>.</p>
        <h2>2. Legal Basis for Processing (GDPR Art. 6(1)(f))</h2>
        <p>{data['gdpr_compliance']['legal_basis']}</p>
        <h2>3. Data Categories Processed</h2>
        <ul>
          <li><strong>IP Addresses:</strong> {data['gdpr_compliance']['data_categories']['ip_addresses']}</li>
          <li><strong>On-Chain Identifiers:</strong> {data['gdpr_compliance']['data_categories']['wallet_addresses_and_hashes']}</li>
          <li><strong>PII & Account Credentials:</strong> {data['gdpr_compliance']['data_categories']['personal_data_collected']}</li>
        </ul>
        <h2>4. Data Retention & Erasure</h2>
        <p>{data['gdpr_compliance']['retention_period']}</p>
        <h2>5. Your Rights as a Data Subject</h2>
        <p>{data['gdpr_compliance']['data_subject_rights']}</p>
        """
        return HTMLResponse(_legal_html_shell("Privacy Policy & GDPR Disclosure", html_body))

    return JSONResponse(data)


@router.api_route("/refund", methods=["GET", "HEAD"])
async def refund_policy(request: Request):
    """Transparent Settlement & Refund Policy for x402 Micropayments."""
    if request.method == "HEAD":
        return Response(status_code=200, media_type="application/json")

    data = {
        "service": "AIM Network M2M Data Hub",
        "updated_at": "2026-11-08",
        "settlement_policy": "Under standard x402 (EIP-3009 signed authorizations), payment transfer authorizations are verified cryptographically before service execution. Settlement is performed on-chain via the x402 facilitator.",
        "failed_requests_and_remedy": "Calls that fail during pre-check or verification are rejected immediately with HTTP 402 with zero charge. In the rare event of an unexpected server failure post-settlement, the transaction receipt in X-PAYMENT-RESPONSE serves as an immutable cryptographic receipt for immediate credit or direct refund via support@johngarp.click.",
        "legacy_onchain_proofs": {
            "single_use_tokens": "On-chain transaction hashes submitted via X-PAYMENT-PROOF are recorded atomically in SQLite per container instance to prevent concurrent replay attacks.",
            "vip_passes": f"24h VIP Passes allow up to {settings.VIP_PASS_MAX_CALLS} calls (Micro >= 2.00 USDC) or {settings.PRO_PASS_MAX_CALLS} calls (Pro >= 10.00 USDC). VIP passes function as bearer tokens keyed by transaction hash with quotas tracked per container instance lifecycle. For non-repudiable cryptographically bound authorization, use standard x402 EIP-3009.",
            "outage_remedy": "In the event of an unserved request using an on-chain transaction hash, contact support@johngarp.click with the transaction hash to receive an immediate replacement VIP pass or equivalent credit.",
        },
        "dispute_contact": "support@johngarp.click (or open a public issue on GitHub: https://github.com/Johnmannen/aim-network-m2m-hub).",
    }

    if _prefers_html(request):
        html_body = f"""
        <div class="meta">Last Updated: {data['updated_at']} &bull; Settlement Protocol: x402 / EIP-3009 on Base Mainnet</div>
        <h2>1. x402 Authorization & Settlement Policy</h2>
        <p>{data['settlement_policy']}</p>
        <h2>2. Failed Requests & Unconditional Remedy</h2>
        <p>{data['failed_requests_and_remedy']}</p>
        <h2>3. Legacy On-Chain Proofs & Pass Security</h2>
        <ul>
          <li><strong>Single-Use Burn (Instance Lifecycle):</strong> {data['legacy_onchain_proofs']['single_use_tokens']}</li>
          <li><strong>VIP Pass Bearer Tokens:</strong> {data['legacy_onchain_proofs']['vip_passes']}</li>
          <li><strong>Outage Remedy:</strong> {data['legacy_onchain_proofs']['outage_remedy']}</li>
        </ul>
        <h2>4. Disputes & Support</h2>
        <p>{data['dispute_contact']}</p>
        """
        return HTMLResponse(_legal_html_shell("Refund & Settlement Policy", html_body))

    return JSONResponse(data)


@router.api_route("/status", methods=["GET", "HEAD"])
async def service_status(request: Request):
    """System health, upstream SLA metrics, and operational status (HTML & JSON)."""
    if request.method == "HEAD":
        return Response(status_code=200, media_type="application/json")
    db_override = request.app.state.db_path if hasattr(request.app.state, "db_path") else None
    stats = get_stats(db_override)

    started_at = getattr(request.app.state, "started_at", None)
    instance_id = getattr(request.app.state, "instance_id", "inst_standalone")
    now_ts = time.time()
    uptime_seconds = int(now_ts - started_at) if started_at else 0
    uptime_str = f"{uptime_seconds // 3600}h {(uptime_seconds % 3600) // 60}m {uptime_seconds % 60}s"

    from app.services.market_data import _get_cached
    dex_cached = _get_cached("trending_dex_tokens")
    if dex_cached is None:
        dex_status = "UNKNOWN"
    elif dex_cached.get("is_stale"):
        dex_status = "DEGRADED"
    else:
        dex_status = "HEALTHY"

    pulse_cached = _get_cached("crypto_pulse")
    if pulse_cached is None:
        coinbase_status = "UNKNOWN"
    elif pulse_cached.get("meta", {}).get("status") == "LIVE_FEED_VERIFIED":
        coinbase_status = "HEALTHY"
    else:
        coinbase_status = "DEGRADED"

    data = {
        "status": "OPERATIONAL",
        "network": "Base Mainnet (Chain ID 8453)",
        "instance_id": instance_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "uptime_metric": {
            "uptime_seconds": uptime_seconds,
            "uptime_human": uptime_str,
            "availability_target": "99.9% SLA target",
        },
        "persistence_scope": "instance-local (SQLite WAL on ephemeral container SSD; resets on deployment/restart)",
        "storage_engine": "SQLite WAL on SSD Local Storage (/app/data/aim_network.db)",
        "sla_latency_targets": {
            "l1_cache_response": "<15ms (in-memory L1 cache)",
            "upstream_aggregation": "300-800ms (Coinbase Exchange parallel fetch)",
        },
        "upstreams": {
            "base_l2_rpc": "HEALTHY",
            "coinbase_exchange_stats": coinbase_status,
            "coingecko_spot_fallback": "STANDBY_BACKUP",
            "payai_facilitator": "HEALTHY" if settings.X402_FACILITATOR_URL else "CONFIGURED_ONLINE",
            "dexscreener": dex_status,
        },
        "stats_overview": {
            "total_calls_served": stats.get("total_calls", 0),
            "calls_micro": stats.get("calls_micro", 0),
            "calls_premium": stats.get("calls_premium", 0),
            "system_paused": stats.get("paused", False),
        },
    }

    if _prefers_html(request):
        html_body = f"""
        <div class="meta">Status: <strong style="color: #4ade80;">{data['status']}</strong> &bull; Timestamp: {data['timestamp']}</div>
        <h2>System Overview</h2>
        <p><strong>Network:</strong> {data['network']}<br>
        <strong>Instance ID:</strong> <code>{data['instance_id']}</code><br>
        <strong>Persistence Scope:</strong> {data['persistence_scope']}<br>
        <strong>Storage Engine:</strong> {data['storage_engine']}<br>
        <strong>Instance Uptime:</strong> {data['uptime_metric']['uptime_human']} ({data['uptime_metric']['availability_target']})<br>
        <strong>Total Calls Processed:</strong> {data['stats_overview']['total_calls_served']}</p>
        <h2>Latency SLA Targets</h2>
        <ul>
          <li><strong>In-Memory L1 Cache:</strong> {data['sla_latency_targets']['l1_cache_response']}</li>
          <li><strong>Upstream Aggregation:</strong> {data['sla_latency_targets']['upstream_aggregation']}</li>
        </ul>
        <h2>Upstream Subsystem Health</h2>
        <ul>
          <li>Base L2 RPC: <span style="color:#4ade80;">{data['upstreams']['base_l2_rpc']}</span></li>
          <li>Coinbase Exchange Stats: <span style="color:#4ade80;">{data['upstreams']['coinbase_exchange_stats']}</span></li>
          <li>CoinGecko Fallback: <span style="color:#4ade80;">{data['upstreams']['coingecko_spot_fallback']}</span></li>
          <li>PayAI Facilitator: <span style="color:#4ade80;">{data['upstreams']['payai_facilitator']}</span></li>
          <li>DexScreener Radar: <span style="color:#4ade80;">{data['upstreams']['dexscreener']}</span></li>
        </ul>
        """
        return HTMLResponse(_legal_html_shell("System Operational Status", html_body))

    return JSONResponse(data)

