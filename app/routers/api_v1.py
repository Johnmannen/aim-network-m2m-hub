"""
M2M Paid API Endpoints (Tier 1: $0.01 USDC & Tier 2: $1.00 USDC).
Protected by x402 Payment Protocol on Base L2.
"""

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
    teaser_data = {
        "status": "LIVE_FEED_VERIFIED",
        "price_usdc": 0.0,
        "timestamp": pulse["timestamp"],
        "btc_spot_preview_usd": pulse["assets"]["BTC"]["price_usd"],
        "market_sentiment_preview": pulse["market_sentiment"],
        "sample_preview_param": "Add ?sample=true to any paid endpoint to inspect payload schema without x402 payment",
        "schema_sample": {
            "crypto_pulse": {
                "assets": {"BTC": {"price_usd": 89450.0, "change_24h_pct": 1.2, "volume_24h_usd": 45000000000}},
                "volatility_index": {"level": "MODERATE", "score": 42.5},
                "market_sentiment": "bullish",
            },
            "base_dex_radar": {
                "top_pairs": [{"pair": "WETH/USDC", "dex": "aerodrome", "volume_24h_usd": 12000000, "whale_net_inflow_usd": 450000}],
                "whale_signals": ["AERODROME_HIGH_LIQUIDITY_DEPTH"],
            },
        },
        "locked_premium_fields": [
            "ETH & SOL 24h volume & volatility matrix (/api/v1/crypto-pulse -> 0.01 USDC)",
            "Base L2 DEX Whale Liquidity & Top Pools (/api/v1/base-dex-radar -> 0.05 USDC)",
            "Institutional M2M Quantitative Signals (/api/v1/deep-market-report -> 1.00 USDC)",
            "24h All-Access VIP Pass (1,000 calls across all endpoints -> 2.00 USDC)",
        ],
        "payment_recipient_base_usdc": settings.WALLET_ADDRESS,
        "x402_network": "base-mainnet (Chain ID 8453)",
    }
    if request.method == "HEAD":
        return Response(status_code=200, media_type="application/json")
    return teaser_data


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
        data = await fetch_base_dex_radar()
        return {
            "status": "SAMPLE_DATA_VERIFIED",
            "sample_mode": True,
            "sample_notice": "SAMPLE ONLY: Live DEX whale radar requires 0.05 USDC via x402 on Base.",
            "feed": "/api/v1/base-dex-radar",
            "live_price_usdc": settings.PRICE_DEX_RADAR_USDC,
            "payload": data,
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
        data = await fetch_crypto_pulse_data()
        return {
            "status": "SAMPLE_DATA_VERIFIED",
            "sample_mode": True,
            "sample_notice": "SAMPLE ONLY: Real-time feeds require 0.01 USDC via x402 on Base. Pass X-PAYMENT or X-PAYMENT-PROOF.",
            "feed": "/api/v1/crypto-pulse",
            "live_price_usdc": settings.PRICE_MICRO_USDC,
            "payload": data,
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
        data = await fetch_deep_market_report()
        return {
            "status": "SAMPLE_DATA_VERIFIED",
            "sample_mode": True,
            "sample_notice": "SAMPLE ONLY: Full quantitative regime report requires 1.00 USDC via x402 on Base.",
            "feed": "/api/v1/deep-market-report",
            "live_price_usdc": settings.PRICE_PREMIUM_USDC,
            "payload": data,
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
        data = await fetch_dynamic_asset_pulse(
            slug=clean_slug,
            asset_name=matched["asset_name"],
            asset_symbol=matched["asset_symbol"],
            coingecko_id=matched["coingecko_id"],
        )
        return {
            "status": "SAMPLE_DATA_VERIFIED",
            "sample_mode": True,
            "sample_notice": f"SAMPLE ONLY: Live {matched['asset_symbol']} orderflow requires {float(price_dec):.2f} USDC via x402.",
            "feed": f"/api/v1/trending/{clean_slug}",
            "live_price_usdc": float(price_dec),
            "payload": data,
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
