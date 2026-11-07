"""
M2M Paid API Endpoints (Tier 1: $0.01 USDC & Tier 2: $1.00 USDC).
Protected by x402 Payment Protocol on Base L2.
"""

from fastapi import APIRouter, HTTPException, Request
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


@router.get("/free-teaser")
async def get_free_teaser():
    """
    Free Zero-Auth Verification Teaser ($0.00 USDC):
    Allows autonomous buying bots to verify <150ms latency and live data freshness before paying via x402.
    """
    pulse = await fetch_crypto_pulse_data()
    return {
        "status": "LIVE_FEED_VERIFIED",
        "price_usdc": 0.0,
        "timestamp": pulse["timestamp"],
        "btc_spot_preview_usd": pulse["assets"]["BTC"]["price_usd"],
        "market_sentiment_preview": pulse["market_sentiment"],
        "locked_premium_fields": [
            "ETH & SOL 24h volume & volatility matrix (/api/v1/crypto-pulse -> 0.01 USDC)",
            "Base L2 DEX Whale Liquidity & Top Pools (/api/v1/base-dex-radar -> 0.05 USDC)",
            "Institutional M2M Quantitative Signals (/api/v1/deep-market-report -> 1.00 USDC)",
            "24h All-Access VIP Pass (1,000 calls across all endpoints -> 2.00 USDC)",
        ],
        "payment_recipient_base_usdc": settings.WALLET_ADDRESS,
    }


@router.get("/base-dex-radar")
async def get_base_dex_radar(request: Request):
    """
    Base L2 DEX Liquidity & Whale Inflow Radar ($0.05 USDC):
    Delivers real-time top Base DEX pools, volume spikes, and whale inflow signals via DexScreener.
    """
    db_override = request.app.state.db_path if hasattr(request.app.state, "db_path") else None
    payment_check = await require_x402_payment(
        request=request,
        price_usdc=settings.PRICE_DEX_RADAR_USDC,
        description="Real-time Base L2 DEX Liquidity Pools & Whale Inflow Radar (JSON)",
        tier="micro",
        db_path=db_override,
    )
    if payment_check:
        return payment_check

    return await fetch_base_dex_radar()


@router.get("/crypto-pulse")
async def get_crypto_pulse(request: Request):
    """
    Tier 1 Micro-API ($0.01 USDC):
    Delivers real-time crypto prices, 24h volatility index, and Fear & Greed sentiment.
    """
    db_override = request.app.state.db_path if hasattr(request.app.state, "db_path") else None
    payment_check = await require_x402_payment(
        request=request,
        price_usdc=settings.PRICE_MICRO_USDC,
        description="Real-time crypto market pulse, sentiment & volatility feed (JSON)",
        tier="micro",
        db_path=db_override,
    )
    if payment_check:
        return payment_check

    return await fetch_crypto_pulse_data()


@router.get("/deep-market-report")
async def get_deep_market_report(request: Request):
    """
    Tier 2 Premium-API ($1.00 USDC):
    Delivers deep quantitative M2M market analysis, Base L2 liquidity metrics, and actionable signals.
    """
    db_override = request.app.state.db_path if hasattr(request.app.state, "db_path") else None
    payment_check = await require_x402_payment(
        request=request,
        price_usdc=settings.PRICE_PREMIUM_USDC,
        description="Deep AI & Quantitative M2M Market & Base Liquidity Report (JSON)",
        tier="premium",
        db_path=db_override,
    )
    if payment_check:
        return payment_check

    return await fetch_deep_market_report()


@router.get("/trending/{slug}")
async def get_dynamic_trending_endpoint(slug: str, request: Request):
    """
    Auto-Deployed Scout Endpoint ($0.05 USDC):
    Delivers real-time orderflow, price, and momentum for trending assets discovered by the Autonomous Scout.
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

    price = float(matched.get("price_usdc", settings.PRICE_DYNAMIC_USDC))
    payment_check = await require_x402_payment(
        request=request,
        price_usdc=price,
        description=f"Live trending pulse & orderflow for {matched['asset_name']} ({matched['asset_symbol']})",
        tier="micro",
        db_path=db_override,
    )
    if payment_check:
        return payment_check

    increment_dynamic_endpoint_stats(clean_slug, price, db_override)
    return await fetch_dynamic_asset_pulse(
        slug=clean_slug,
        asset_name=matched["asset_name"],
        asset_symbol=matched["asset_symbol"],
        coingecko_id=matched["coingecko_id"],
    )


