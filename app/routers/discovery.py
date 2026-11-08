"""
Self-Marketing & AI Agent Discovery Router:
- GET /llms.txt (Standard LLM manifest for OpenAI, Anthropic, Perplexity & M2M crawlers)
- GET /agents.json (x402 & MCP catalog specification — dynamically includes Scout-built endpoints)
- GET /.well-known/agent.json (A2A Agent Card specification)
- GET/POST /cron/discover (Autonomous Scout trigger)
"""

import json
import secrets
from decimal import Decimal
from typing import Any, Optional
from fastapi import APIRouter, Header, HTTPException, Request
from fastapi.responses import JSONResponse, PlainTextResponse, Response

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
## Welcome Bonus: First-Time Buyer Campaign (Buy 1, Get 5 Free)
- New wallet addresses that make their first USDC purchase on ANY endpoint automatically unlock **5 FREE bonus calls** across all micro feeds ($0.01-$0.05) for 24 hours.
- Reuse the same `tx_hash` in `X-PAYMENT-PROOF: <tx_hash>` to consume your 5 bonus calls.

## Volume Discount: 24-Hour VIP Passes
- **24-Hour Micro VIP Pass (`{settings.PRICE_VIP_24H_USDC:.2f} USDC`):** Send `{settings.PRICE_VIP_24H_USDC:.2f} USDC` on Base to `{settings.WALLET_ADDRESS}` and reuse the same `X-PAYMENT-PROOF` transaction hash for up to **{settings.VIP_PASS_MAX_CALLS} calls across all micro feeds ($0.01-$0.05) for 24 hours**.
- **24-Hour Pro VIP Pass (`10.00 USDC`):** Full 24h unlimited access to all endpoints including Deep Market Reports ($1.00) up to 500 calls.

## Machine Catalogs
- Agent Catalog: `/agents.json`
- MCP Server Manifest & JSON-RPC: `/mcp`
- A2A Agent Card: `/.well-known/agent.json`
- Trending Assets Index: `/api/v1/trending`
- OpenAPI Schema: `/openapi.json`

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
        "$schema": "https://a2a-standard.org/schemas/agent-card.json",
        "name": "AIM Network M2M Hub",
        "description": "Autonomous quantitative market data, Base L2 DEX whale radar, and orderflow analytics payable via HTTP 402 (x402) on Base.",
        "version": settings.VERSION,
        "url": "https://johngarp.click",
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
        "provider": {
            "organization": "AIM Network",
            "url": "https://johngarp.click",
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
            },
            {
                "id": "crypto-pulse",
                "name": "Crypto Market Pulse",
                "description": "Real-time BTC/ETH/SOL market pulse, sentiment, and volatility metrics.",
                "url": "https://johngarp.click/api/v1/crypto-pulse",
                "cost_usdc": 0.01,
            },
            {
                "id": "base-dex-radar",
                "name": "Base L2 DEX Whale Radar",
                "description": "Base L2 DEX liquidity pools, volume spikes, and whale orderflow tracking.",
                "url": "https://johngarp.click/api/v1/base-dex-radar",
                "cost_usdc": 0.05,
            },
            {
                "id": "deep-market-report",
                "name": "Deep Market Quantitative Analysis",
                "description": "Quantitative regime detection, momentum scoring, and actionable signals.",
                "url": "https://johngarp.click/api/v1/deep-market-report",
                "cost_usdc": 1.00,
            },
            {
                "id": "trending",
                "name": "Trending Tokens Index",
                "description": "Free public index of active momentum tokens on Base L2.",
                "url": "https://johngarp.click/api/v1/trending",
                "cost_usdc": 0.0,
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
                client_proto = (
                    params.get("protocolVersion")
                    if isinstance(params, dict)
                    else None
                ) or "2024-11-05"
                return JSONResponse(
                    {
                        "jsonrpc": "2.0",
                        "id": rpc_id,
                        "result": {
                            "protocolVersion": client_proto,
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

