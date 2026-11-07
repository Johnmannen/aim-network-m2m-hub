"""
Self-Marketing & AI Agent Discovery Router:
- GET /llms.txt (Standard LLM manifest for OpenAI, Anthropic, Perplexity & M2M crawlers)
- GET /agents.json (x402 & MCP catalog specification — dynamically includes Scout-built endpoints)
- GET /.well-known/agent.json (A2A Agent Card specification)
- GET/POST /cron/discover (Autonomous Scout trigger)
"""

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, PlainTextResponse

from app.config import settings
from app.database import get_stats
from app.services.scout import run_autonomous_scout

router = APIRouter(tags=["AI Discovery & Autonomous Scout"])


@router.get("/llms.txt", response_class=PlainTextResponse)
async def llms_txt_manifest(request: Request) -> str:
    """Machine-readable Markdown manifest for LLM crawlers and autonomous buying agents."""
    db_override = request.app.state.db_path if hasattr(request.app.state, "db_path") else None
    stats = get_stats(db_override)
    dynamic_lines = ""
    idx = 3
    for ep in stats.get("dynamic_endpoints", []):
        dynamic_lines += (
            f"{idx}. `GET {ep['endpoint_path']}`\n"
            f"   - **Price:** `{ep['price_usdc']:.2f} USDC`\n"
            f"   - **Description:** Auto-deployed live trending pulse & orderflow for {ep['asset_name']} ({ep['asset_symbol']}).\n"
        )
        idx += 1

    return f"""# AIM Network — Autonomous M2M API Hub
> Ultra-fast (<150ms cached) machine-payable data endpoints via HTTP 402 (x402 protocol) on Base Mainnet (Chain ID 8453).
> No account or API key required. Pay per call in USDC on Base and pass transaction hash in `X-PAYMENT-PROOF` header.

## Payment Configuration (x402 v1.0)
- **Network:** `base-mainnet` (Chain ID: `8453`)
- **Token:** `USDC` (`{settings.USDC_CONTRACT_ADDRESS}`)
- **Recipient Wallet:** `{settings.WALLET_ADDRESS}`
- **Proof Header:** `X-PAYMENT-PROOF: <0x_base_transaction_hash>`

## Available M2M Endpoints
0. `GET /api/v1/free-teaser`
   - **Price:** `0.00 USDC (FREE)`
   - **Description:** Instant live BTC spot & latency verification teaser for autonomous agents.
1. `GET /api/v1/crypto-pulse`
   - **Price:** `{settings.PRICE_MICRO_USDC:.2f} USDC`
   - **Description:** Real-time BTC/ETH/SOL prices, 24h volatility index, and Fear & Greed sentiment JSON.
2. `GET /api/v1/base-dex-radar`
   - **Price:** `{settings.PRICE_DEX_RADAR_USDC:.2f} USDC`
   - **Description:** Real-time Base L2 DEX liquidity pools, volume spikes, and whale inflow radar via DexScreener.
3. `GET /api/v1/deep-market-report`
   - **Price:** `{settings.PRICE_PREMIUM_USDC:.2f} USDC`
   - **Description:** Institutional M2M quantitative market regime, Base L2 liquidity metrics, and actionable trading signals JSON.
{dynamic_lines}
## Volume Discount: 24-Hour VIP Pass (`{settings.PRICE_VIP_24H_USDC:.2f} USDC`)
- Send `{settings.PRICE_VIP_24H_USDC:.2f} USDC` on Base to `{settings.WALLET_ADDRESS}` and reuse the same `X-PAYMENT-PROOF` transaction hash for up to **{settings.VIP_PASS_MAX_CALLS} calls across ALL endpoints for 24 hours**.

## Machine Catalogs
- Agent Catalog: `/agents.json`
- MCP Server Manifest & JSON-RPC: `/mcp`
- A2A Agent Card: `/.well-known/agent.json`
- OpenAPI Schema: `/openapi.json`
"""


@router.get("/robots.txt", response_class=PlainTextResponse)
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


@router.get("/sitemap.xml")
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
        f"{base}/api/v1/crypto-pulse",
        f"{base}/api/v1/deep-market-report",
    ]
    for ep in stats.get("dynamic_endpoints", []):
        urls.append(f"{base}{ep['endpoint_path']}")
    xml_items = "".join(f"<url><loc>{u}</loc></url>" for u in urls)
    xml = f'<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{xml_items}</urlset>'
    return Response(content=xml, media_type="application/xml")


@router.get("/agents.json", response_class=JSONResponse)
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
        "discovery": {
            "llms_txt": "/llms.txt",
            "openapi_url": "/openapi.json",
            "well_known_agent": "/.well-known/agent.json",
        },
    }


@router.get("/.well-known/agent.json", response_class=JSONResponse)
async def well_known_agent_card(request: Request) -> dict:
    """A2A-compatible Agent Card for autonomous multi-agent ecosystems."""
    return await agents_json_manifest(request)


@router.api_route("/cron/discover", methods=["GET", "POST"], response_class=JSONResponse)
async def trigger_autonomous_scout(request: Request) -> dict:
    """Run the Autonomous Scout to discover AND auto-deploy a new M2M API endpoint."""
    db_override = request.app.state.db_path if hasattr(request.app.state, "db_path") else None
    entry = await run_autonomous_scout(db_path=db_override)
    return {
        "status": "success",
        "message": "Autonomous Scout discovered and auto-deployed a live M2M API endpoint.",
        "discovery": entry,
    }


@router.api_route("/mcp", methods=["GET", "POST"], response_class=JSONResponse)
async def mcp_server_endpoint(request: Request) -> dict:
    """
    Model Context Protocol (MCP) Discovery & Tool Definition Endpoint.
    Allows MCP directories (Smithery, mcp.so, Glama) and LLM agents to inspect and invoke AIM Network tools.
    """
    tools = [
        {
            "name": "get_free_market_teaser",
            "description": "Free instant verification of live BTC spot price and M2M feed status ($0.00 USDC).",
            "endpoint": "https://johngarp.click/api/v1/free-teaser",
            "price_usdc": 0.0,
        },
        {
            "name": "get_crypto_pulse",
            "description": "Real-time BTC, ETH, SOL prices, 24h volatility index, and Fear & Greed sentiment ($0.01 USDC via x402 on Base).",
            "endpoint": "https://johngarp.click/api/v1/crypto-pulse",
            "price_usdc": settings.PRICE_MICRO_USDC,
        },
        {
            "name": "get_base_dex_radar",
            "description": "Real-time Base L2 DEX liquidity pools, volume spikes, and whale inflow signals ($0.05 USDC via x402 on Base).",
            "endpoint": "https://johngarp.click/api/v1/base-dex-radar",
            "price_usdc": settings.PRICE_DEX_RADAR_USDC,
        },
        {
            "name": "get_deep_market_report",
            "description": "Institutional M2M quantitative market regime, Base L2 liquidity metrics, and actionable trading signals ($1.00 USDC via x402 on Base).",
            "endpoint": "https://johngarp.click/api/v1/deep-market-report",
            "price_usdc": settings.PRICE_PREMIUM_USDC,
        },
    ]
    return {
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

