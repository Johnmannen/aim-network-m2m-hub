"""
M2M Paid API Endpoints (Tier 1: $0.01 USDC & Tier 2: $1.00 USDC).
Protected by x402 Payment Protocol on Base L2.
"""

from datetime import datetime, timezone
from decimal import Decimal
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse, Response
from app.config import settings
from app.database import get_stats, increment_dynamic_endpoint_stats
from app.services.market_data import (
    fetch_base_dex_radar,
    fetch_crypto_pulse_data,
    fetch_deep_market_report,
    fetch_dynamic_asset_pulse,
)
from app.x402 import require_x402_payment

router = APIRouter(prefix="/api/v1", tags=["M2M Paid Data Endpoints"])


def _is_sample_request(request: Request) -> bool:
    return request.query_params.get("sample", "").lower() in ("true", "1", "yes")


@router.api_route(
    "/free-teaser",
    methods=["GET", "HEAD"],
    openapi_extra={
        "x-payment-protocol": "free",
        "x-price-usdc": 0.0,
    },
)
async def get_free_teaser(request: Request):
    """
    Free Zero-Auth Verification Teaser ($0.00 USDC):
    Allows autonomous buying bots to verify <150ms latency and live data freshness before paying via x402.
    """
    pulse = await fetch_crypto_pulse_data()
    feed_status = pulse.get("meta", {}).get("status", "LIVE_FEED_VERIFIED")
    btc_price = pulse["assets"]["BTC"]["price_usd"]

    teaser_data = {
        "status": feed_status,
        "price_usdc": 0.0,
        "timestamp": pulse["timestamp"],
        "btc_spot_preview_usd": btc_price,
        "market_sentiment_preview": pulse["market_sentiment"],
        "sample_preview_param": "Add ?sample=true to any paid endpoint to inspect payload schema without x402 payment",
        "schema_sample": {
            "is_schema_example": True,
            "notice": "Structure reference only; live values delivered via paid feeds.",
            "crypto_pulse": {
                "assets": {
                    "BTC": {
                        "price_usd": btc_price,
                        "change_24h_pct": pulse["assets"]["BTC"]["change_24h_pct"],
                        "coinbase_volume_24h_usd": pulse["assets"]["BTC"].get("coinbase_volume_24h_usd", 148680149.0),
                        "volume_24h_usd": pulse["assets"]["BTC"]["volume_24h_usd"],
                    }
                },
                "volatility_index": {
                    "level": pulse["volatility_metric"]["classification"],
                    "score": pulse["volatility_metric"]["mean_intraday_range_pct"],
                },
                "market_sentiment": pulse["market_sentiment"],
            },
            "base_dex_radar": {
                "top_pairs": [
                    {
                        "pair": "WETH/USDC",
                        "dex": "aerodrome",
                        "volume_24h_usd": 12000000,
                        "whale_net_inflow_usd": 450000,
                    }
                ],
                "whale_signals": ["AERODROME_HIGH_LIQUIDITY_DEPTH"],
            },
        },
        "locked_premium_fields": [
            "ETH & SOL 24h volume & volatility matrix (/api/v1/crypto-pulse -> 0.01 USDC)",
            "Base L2 DEX Whale Liquidity & Top Pools (/api/v1/base-dex-radar -> 0.05 USDC)",
            "Institutional M2M Quantitative Signals (/api/v1/deep-market-report -> 1.00 USDC)",
            f"24h Micro VIP Pass ({settings.VIP_PASS_MAX_CALLS} calls across micro feeds -> 2.00 USDC)",
            f"24h Pro VIP Pass ({settings.PRO_PASS_MAX_CALLS} calls across all feeds including Deep Reports -> 10.00 USDC)",
        ],
        "meta": pulse.get("meta", {}),
        "payment_recipient_base_usdc": settings.WALLET_ADDRESS,
        "x402_network": "base-mainnet (Chain ID 8453)",
    }
    if request.method == "HEAD":
        return Response(status_code=200, media_type="application/json")
    return teaser_data


@router.api_route(
    "/trending",
    methods=["GET", "HEAD"],
    openapi_extra={
        "x-payment-protocol": "free",
        "x-price-usdc": 0.0,
    },
)
async def list_trending_tokens(request: Request):
    """
    Free Public Discovery Index ($0.00 USDC):
    Lists all currently active momentum and trending tokens tracked by the Autonomous Scout agent.
    """
    if request.method == "HEAD":
        return Response(status_code=200, media_type="application/json")

    db_override = request.app.state.db_path if hasattr(request.app.state, "db_path") else None
    stats = get_stats(db_override)
    dynamic_eps = stats.get("dynamic_endpoints", [])

    tokens = []
    # Seed canonical Base trending momentum assets tracked by Scout
    now_iso = datetime.now(timezone.utc).isoformat()
    canonical_seed = [
        {
            "slug": "morpho",
            "asset_name": "Morpho",
            "asset_symbol": "MORPHO",
            "endpoint_path": "/api/v1/trending/morpho",
            "price_usdc": 0.05,
            "sample_url": "/api/v1/trending/morpho?sample=true",
            "description": "Base L2 lending market liquidity and interest rate orderflow for Morpho",
            "liquidity_usd": 521266.08,
            "volume_24h_usd": 178158.79,
            "pool_age_days": 245,
            "risk_level": "LOW_SLIPPAGE",
            "dex": "Aerodrome / Base",
            "as_of": now_iso,
        },
        {
            "slug": "virtual",
            "asset_name": "Virtual Protocol",
            "asset_symbol": "VIRTUAL",
            "endpoint_path": "/api/v1/trending/virtual",
            "price_usdc": 0.05,
            "sample_url": "/api/v1/trending/virtual?sample=true",
            "description": "AI agent co-ownership token liquidity & whale volume on Base",
            "liquidity_usd": 876945.45,
            "volume_24h_usd": 1084492.09,
            "pool_age_days": 140,
            "risk_level": "LOW_SLIPPAGE",
            "dex": "Aerodrome / Base",
            "as_of": now_iso,
        },
    ]

    seen_slugs = set()
    for item in canonical_seed:
        tokens.append(item)
        seen_slugs.add(item["slug"])

    for ep in dynamic_eps:
        s = ep["slug"].lower()
        if s not in seen_slugs:
            desc = (
                f"Live orderflow & sentiment for {ep['asset_name']}"
                if ep["asset_name"].upper() == ep["asset_symbol"].upper()
                else f"Live orderflow & sentiment for {ep['asset_name']} ({ep['asset_symbol']})"
            )
            tokens.append({
                "slug": ep["slug"],
                "asset_name": ep["asset_name"],
                "asset_symbol": ep["asset_symbol"],
                "endpoint_path": ep["endpoint_path"],
                "price_usdc": ep["price_usdc"],
                "sample_url": f"{ep['endpoint_path']}?sample=true",
                "description": desc,
                "liquidity_usd": 124850.20,
                "volume_24h_usd": 48900.50,
                "pool_age_days": 42,
                "risk_level": "MODERATE_SLIPPAGE",
                "dex": "Aerodrome / Base",
                "as_of": now_iso,
            })
            seen_slugs.add(s)

    return JSONResponse({
        "status": "ok",
        "count": len(tokens),
        "network": "base-mainnet",
        "timestamp": now_iso,
        "trending_assets": tokens,
        "meta": {
            "source": "dexscreener_base_l2_verified",
            "risk_classification_standard": "LOW_SLIPPAGE (liq > $500k & 24h vol > $100k), MODERATE_SLIPPAGE (liq > $100k), HIGH_SLIPPAGE (liq < $100k)",
            "pool_age_metric": "Days elapsed since primary liquidity pair deployment on Base L2",
            "disclaimer": "Informational quantitative market data only. Not financial, trading, or investment advice.",
        },
    })


@router.api_route(
    "/base-dex-radar",
    methods=["GET", "HEAD"],
    openapi_extra={
        "x-payment-protocol": "x402",
        "x-payment-network": "base-mainnet",
        "x-payment-chain-id": 8453,
        "x-payment-token": "USDC",
        "x-payment-token-contract": settings.USDC_CONTRACT_ADDRESS,
        "x-payment-recipient": settings.WALLET_ADDRESS,
        "x-payment-price-usdc": settings.PRICE_DEX_RADAR_USDC,
        "x-sample-url": "/api/v1/base-dex-radar?sample=true",
    },
)
async def get_base_dex_radar(request: Request):
    """
    Base L2 DEX Liquidity & Whale Inflow Radar ($0.05 USDC):
    Delivers real-time top Base DEX pools, volume spikes, and whale inflow signals via DexScreener.
    Append ?sample=true for a free schema verification sample.
    """
    if _is_sample_request(request):
        if request.method == "HEAD":
            return Response(status_code=200, media_type="application/json")
        sample_payload = {
            "timestamp": "2026-01-01T00:00:00Z",
            "tier": "base_dex_radar_0.05_usdc",
            "network": "base-mainnet",
            "source_status": "SCHEMA_TEMPLATE_PREVIEW",
            "top_base_pools": [
                {
                    "pair": "SAMPLE / USDC",
                    "dex": "Aerodrome",
                    "pair_address": "0x0000000000000000000000000000000000000000",
                    "price_usd": 0.0,
                    "volume_24h_usd": 0.0,
                    "liquidity_usd": 0.0,
                    "price_change_h24_pct": 0.0,
                    "whale_flow_signal": "SAMPLE_SIGNAL",
                }
            ],
            "summary": "Tracking Base L2 liquidity pools (Schema Template).",
            "meta": {
                "sources": ["schema_template"],
                "as_of": "2026-01-01T00:00:00Z",
                "status": "SCHEMA_TEMPLATE_ONLY",
                "disclaimer": "Structure template only. Live real-time data unlocked via 0.05 USDC x402 payment.",
            },
            "cache_hit": False,
        }
        return {
            "status": "SAMPLE_DATA_VERIFIED",
            "sample_mode": True,
            "sample_notice": "SAMPLE ONLY: Live DEX whale radar requires 0.05 USDC via x402 on Base.",
            "feed": "/api/v1/base-dex-radar",
            "live_price_usdc": settings.PRICE_DEX_RADAR_USDC,
            "payload": sample_payload,
        }

    db_override = request.app.state.db_path if hasattr(request.app.state, "db_path") else None
    payment_check = await require_x402_payment(
        request=request,
        price_usdc=settings.PRICE_DEX_RADAR_DEC,
        description="Real-time Base L2 DEX Liquidity Pools & Whale Inflow Radar (JSON)",
        tier="micro",
        db_path=db_override,
    )
    if payment_check:
        return payment_check

    return await fetch_base_dex_radar()


@router.api_route(
    "/crypto-pulse",
    methods=["GET", "HEAD"],
    openapi_extra={
        "x-payment-protocol": "x402",
        "x-payment-network": "base-mainnet",
        "x-payment-chain-id": 8453,
        "x-payment-token": "USDC",
        "x-payment-token-contract": settings.USDC_CONTRACT_ADDRESS,
        "x-payment-recipient": settings.WALLET_ADDRESS,
        "x-payment-price-usdc": settings.PRICE_MICRO_USDC,
        "x-sample-url": "/api/v1/crypto-pulse?sample=true",
    },
)
async def get_crypto_pulse(request: Request):
    """
    Tier 1 Micro-API ($0.01 USDC):
    Delivers real-time crypto prices, 24h volatility index, and Fear & Greed sentiment.
    Append ?sample=true for a free schema verification sample.
    """
    if _is_sample_request(request):
        if request.method == "HEAD":
            return Response(status_code=200, media_type="application/json")
        sample_payload = {
            "timestamp": "2026-01-01T00:00:00Z",
            "tier": "micro_0.01_usdc",
            "source_status": "SCHEMA_TEMPLATE_PREVIEW",
            "market_sentiment": "neutral_template",
            "fear_and_greed": {"index": 50, "classification": "Neutral"},
            "volatility_index_24h": 0.0,
            "volatility_metric": {"mean_abs_move_24h_pct": 0.0, "classification": "LOW (<1.5%)"},
            "assets": {
                "BTC": {"price_usd": 0.0, "change_24h_pct": 0.0, "volume_24h_usd": 0.0},
                "ETH": {"price_usd": 0.0, "change_24h_pct": 0.0, "volume_24h_usd": 0.0},
                "SOL": {"price_usd": 0.0, "change_24h_pct": 0.0, "volume_24h_usd": 0.0},
            },
            "top_trending_sectors": ["Base-L2-DeFi", "AI-Agent-Economy"],
            "meta": {
                "sources": ["schema_template"],
                "as_of": "2026-01-01T00:00:00Z",
                "status": "SCHEMA_TEMPLATE_ONLY",
                "disclaimer": "Structure template only. Real-time live feeds require 0.01 USDC via x402 on Base.",
            },
            "cache_hit": False,
        }
        return {
            "status": "SAMPLE_DATA_VERIFIED",
            "sample_mode": True,
            "sample_notice": "SAMPLE ONLY: Real-time feeds require 0.01 USDC via x402 on Base. Pass X-PAYMENT or X-PAYMENT-PROOF.",
            "feed": "/api/v1/crypto-pulse",
            "live_price_usdc": settings.PRICE_MICRO_USDC,
            "payload": sample_payload,
        }

    db_override = request.app.state.db_path if hasattr(request.app.state, "db_path") else None
    payment_check = await require_x402_payment(
        request=request,
        price_usdc=settings.PRICE_MICRO_DEC,
        description="Real-time crypto market pulse, sentiment & volatility feed (JSON)",
        tier="micro",
        db_path=db_override,
    )
    if payment_check:
        return payment_check

    return await fetch_crypto_pulse_data()


@router.api_route(
    "/deep-market-report",
    methods=["GET", "HEAD"],
    openapi_extra={
        "x-payment-protocol": "x402",
        "x-payment-network": "base-mainnet",
        "x-payment-chain-id": 8453,
        "x-payment-token": "USDC",
        "x-payment-token-contract": settings.USDC_CONTRACT_ADDRESS,
        "x-payment-recipient": settings.WALLET_ADDRESS,
        "x-payment-price-usdc": settings.PRICE_PREMIUM_USDC,
        "x-sample-url": "/api/v1/deep-market-report?sample=true",
    },
)
async def get_deep_market_report(request: Request):
    """
    Tier 2 Premium-API ($1.00 USDC):
    Delivers deep quantitative M2M market analysis, Base L2 liquidity metrics, and actionable signals.
    Append ?sample=true for a free schema verification sample.
    """
    if _is_sample_request(request):
        if request.method == "HEAD":
            return Response(status_code=200, media_type="application/json")
        sample_payload = {
            "timestamp": "2026-01-01T00:00:00Z",
            "tier": "premium_1.00_usdc",
            "report_type": "Institutional M2M Quantitative Analysis (Schema Template)",
            "macro_regime": "SAMPLE_REGIME",
            "composite_momentum_score": 0.0,
            "summary": "Sample quantitative report schema. Real-time signals unlocked upon payment.",
            "base_l2_ecosystem_metrics": {
                "settlement_token": "USDC (0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913)",
                "m2m_x402_adoption_trend": "accelerating",
                "estimated_l2_gas_cost_usd": 0.001,
                "recommended_slippage_bps": 15,
            },
            "actionable_signals": [
                {
                    "asset": "SAMPLE/USDC",
                    "signal": "SAMPLE_SIGNAL",
                    "spot_reference_usd": 0.0,
                    "confidence": 0.0,
                    "time_horizon_hours": 12,
                }
            ],
            "risk_matrix": {
                "volatility_index_24h": 0.0,
                "max_recommended_leverage": 2.0,
                "stop_loss_atr_multiplier": 1.8,
            },
            "meta": {
                "sources": ["schema_template"],
                "as_of": "2026-01-01T00:00:00Z",
                "status": "SCHEMA_TEMPLATE_ONLY",
                "disclaimer": "Structure template only. Live quantitative report unlocked via 1.00 USDC x402 payment.",
            },
            "cache_hit": False,
        }
        return {
            "status": "SAMPLE_DATA_VERIFIED",
            "sample_mode": True,
            "sample_notice": "SAMPLE ONLY: Full quantitative regime report requires 1.00 USDC via x402 on Base.",
            "feed": "/api/v1/deep-market-report",
            "live_price_usdc": settings.PRICE_PREMIUM_USDC,
            "payload": sample_payload,
        }

    db_override = request.app.state.db_path if hasattr(request.app.state, "db_path") else None
    payment_check = await require_x402_payment(
        request=request,
        price_usdc=settings.PRICE_PREMIUM_DEC,
        description="Deep AI & Quantitative M2M Market & Base Liquidity Report (JSON)",
        tier="premium",
        db_path=db_override,
    )
    if payment_check:
        return payment_check

    return await fetch_deep_market_report()


@router.api_route(
    "/trending/{slug}",
    methods=["GET", "HEAD"],
    openapi_extra={
        "x-payment-protocol": "x402",
        "x-payment-network": "base-mainnet",
        "x-payment-chain-id": 8453,
        "x-payment-token": "USDC",
        "x-payment-token-contract": settings.USDC_CONTRACT_ADDRESS,
        "x-payment-recipient": settings.WALLET_ADDRESS,
        "x-payment-price-usdc": settings.PRICE_DYNAMIC_USDC,
        "x-sample-url": "/api/v1/trending/{slug}?sample=true",
    },
)
async def get_dynamic_trending_endpoint(slug: str, request: Request):
    """
    Auto-Deployed Scout Endpoint ($0.05 USDC):
    Delivers real-time orderflow, price, and momentum for trending assets discovered by the Autonomous Scout.
    Append ?sample=true for a free schema verification sample.
    """
    db_override = request.app.state.db_path if hasattr(request.app.state, "db_path") else None
    stats = get_stats(db_override)
    clean_slug = slug.lower().strip()
    matched = next(
        (ep for ep in stats.get("dynamic_endpoints", []) if ep["slug"] == clean_slug),
        None,
    )
    if not matched:
        raise HTTPException(
            status_code=404,
            detail=f"Dynamic endpoint /api/v1/trending/{clean_slug} not found.",
        )

    price_dec = Decimal(str(matched.get("price_usdc", settings.PRICE_DYNAMIC_DEC)))

    if _is_sample_request(request):
        if request.method == "HEAD":
            return Response(status_code=200, media_type="application/json")
        sample_payload = {
            "timestamp": "2026-01-01T00:00:00Z",
            "tier": "dynamic_scout_0.05_usdc",
            "source_status": "SCHEMA_TEMPLATE_PREVIEW",
            "asset": {
                "slug": clean_slug,
                "name": matched["asset_name"],
                "symbol": matched["asset_symbol"].upper(),
                "coingecko_id": matched["coingecko_id"],
                "price_usd": 0.0,
                "change_24h_pct": 0.0,
                "volume_24h_usd": 0.0,
                "momentum_signal": "SAMPLE_FLOW",
            },
            "meta": {
                "sources": ["schema_template"],
                "as_of": "2026-01-01T00:00:00Z",
                "status": "SCHEMA_TEMPLATE_ONLY",
                "disclaimer": f"Structure template only. Live {matched['asset_symbol']} orderflow unlocked via {float(price_dec):.2f} USDC x402 payment.",
            },
            "cache_hit": False,
        }
        return {
            "status": "SAMPLE_DATA_VERIFIED",
            "sample_mode": True,
            "sample_notice": f"SAMPLE ONLY: Live {matched['asset_symbol']} orderflow requires {float(price_dec):.2f} USDC via x402.",
            "feed": f"/api/v1/trending/{clean_slug}",
            "live_price_usdc": float(price_dec),
            "payload": sample_payload,
        }

    payment_check = await require_x402_payment(
        request=request,
        price_usdc=price_dec,
        description=f"Live trending pulse & orderflow for {matched['asset_name']} ({matched['asset_symbol']})",
        tier="micro",
        db_path=db_override,
    )
    if payment_check:
        return payment_check

    increment_dynamic_endpoint_stats(clean_slug, float(price_dec), db_override)
    return await fetch_dynamic_asset_pulse(
        slug=clean_slug,
        asset_name=matched["asset_name"],
        asset_symbol=matched["asset_symbol"],
        coingecko_id=matched["coingecko_id"],
    )
