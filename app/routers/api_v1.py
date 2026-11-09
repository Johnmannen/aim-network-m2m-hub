"""
M2M Paid API Endpoints (Tier 1: $0.01 USDC & Tier 2: $1.00 USDC).
Protected by x402 Payment Protocol on Base L2.
"""

from datetime import datetime, timezone
from decimal import Decimal
from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import JSONResponse, Response
from app.config import settings
from app.database import get_stats, increment_dynamic_endpoint_stats
from app.services.market_data import (
    PAID_MAX_STALE_AGE_SECONDS,
    fetch_arb_scanner_data,
    fetch_base_dex_radar,
    fetch_crypto_pulse_data,
    fetch_data_quality,
    fetch_deep_market_report,
    fetch_dynamic_asset_pulse,
    fetch_multi_source_dossier,
    fetch_sentiment_signals,
    fetch_trending_dex_tokens,
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
                        "coinbase_volume_24h_usd": pulse["assets"]["BTC"].get("coinbase_volume_24h_usd", 0.0),
                        "coinbase_volume_24h_btc": pulse["assets"]["BTC"].get("coinbase_volume_24h_btc", 0.0),
                    }
                },
                "volatility_index": {
                    "level": pulse["volatility_metric"]["classification"],
                    "score": pulse["volatility_metric"]["parkinson_volatility_pct"],
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
            f"24h Pro VIP Pass ({settings.PRO_PASS_MAX_CALLS} calls across all feeds including Deep Reports -> {float(settings.PRO_PASS_PRICE_DEC):.2f} USDC)",
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

    trending_feed = await fetch_trending_dex_tokens()
    canonical_seed = trending_feed.get("tokens", [])
    data_as_of = trending_feed.get("data_as_of", datetime.now(timezone.utc).isoformat())
    data_age_seconds = trending_feed.get("data_age_seconds", 0)
    source_status = trending_feed.get("source", "dexscreener_base_live")
    now_iso = datetime.now(timezone.utc).isoformat()

    tokens = []
    seen_slugs = set()
    for item in canonical_seed:
        is_synth = bool(item.get("is_synthetic", False))
        item_as_of = item.get("data_as_of") if "data_as_of" in item else data_as_of
        item_age = item.get("data_age_seconds") if "data_age_seconds" in item else data_age_seconds
        tokens.append({
            **item,
            "data_as_of": None if is_synth else item_as_of,
            "data_age_seconds": None if is_synth else item_age,
        })
        seen_slugs.add(item["slug"])

    for ep in dynamic_eps:
        s = ep["slug"].lower()
        if s not in seen_slugs:
            desc = (
                f"Trending asset profile for {ep['asset_name']} ({ep['asset_symbol']}) - orderflow feed pending live market trade"
                if ep["asset_name"].upper() != ep["asset_symbol"].upper()
                else f"Trending asset profile for {ep['asset_name']} - orderflow feed pending live market trade"
            )
            tokens.append({
                "slug": ep["slug"],
                "asset_name": ep["asset_name"],
                "asset_symbol": ep["asset_symbol"],
                "endpoint_path": ep["endpoint_path"],
                "price_usdc": ep["price_usdc"],
                "sample_url": f"{ep['endpoint_path']}?sample=true",
                "description": desc,
                "liquidity_usd": None,
                "volume_24h_usd": None,
                "momentum_24h_pct": None,
                "pool_age_days": None,
                "liquidity_class": None,
                "dex": None,
                "source": "autonomous_scout_seed",
                "is_synthetic": True,
                "data_as_of": None,
                "data_age_seconds": None,
            })
            seen_slugs.add(s)

    return JSONResponse({
        "status": "ok",
        "count": len(tokens),
        "network": "base-mainnet",
        "timestamp": now_iso,
        "data_as_of": data_as_of,
        "data_age_seconds": data_age_seconds,
        "trending_assets": tokens,
        "meta": {
            "source": source_status,
            "fallback_reason": trending_feed.get("fallback_reason"),
            "liquidity_classification_standard": "DEEP_LIQUIDITY (liq > $500k & 24h vol > $100k), MODERATE_LIQUIDITY (liq > $100k), LOW_LIQUIDITY (liq < $100k)",
            "momentum_metric": "24-hour price change percentage on primary DEX pool via DexScreener",
            "pool_age_metric": "Days elapsed since primary liquidity pair deployment on Base L2",
            "disclaimer": "Informational quantitative market data only. Not financial, trading, or investment advice.",
        },
    })


@router.api_route(
    "/vip-pass",
    methods=["GET", "HEAD"],
    openapi_extra={
        "x-payment-protocol": "x402-vip",
        "x-price-usdc": float(settings.PRICE_VIP_24H_DEC),
    },
)
async def vip_pass_status_or_quote(
    request: Request,
    tx_hash: str | None = Query(default=None),
):
    """
    Inspect 24h VIP Pass status and remaining calls.
    Provide pass tx_hash via query parameter (?tx_hash=0x...) or X-PAYMENT-PROOF header.
    Without a valid pass, returns x402 machine-readable pricing and purchase instructions.
    """
    if request.method == "HEAD":
        return Response(status_code=200, media_type="application/json")

    proof = (tx_hash or request.headers.get("X-PAYMENT-PROOF", "")).strip()
    db_override = request.app.state.db_path if hasattr(request.app.state, "db_path") else None
    if proof:
        from app.database import get_vip_pass
        pass_data = get_vip_pass(proof, db_path=db_override)
        if pass_data:
            now_dt = datetime.now(timezone.utc)
            expires_dt = datetime.fromisoformat(pass_data["expires_at"])
            is_expired = now_dt >= expires_dt
            remaining = 0 if is_expired else max(0, pass_data["max_calls"] - pass_data["calls_used"])
            if is_expired:
                status_label = "expired"
            elif remaining <= 0:
                status_label = "exhausted"
            else:
                status_label = "active"
            return JSONResponse({
                "status": status_label,
                "is_expired": is_expired,
                "calls_remaining": remaining,
                "vip_pass": pass_data,
            })
        return JSONResponse(status_code=404, content={"error": "VIP pass not found for the provided transaction hash."})

    from app.x402 import build_402_response
    return build_402_response(
        price_usdc=settings.PRICE_VIP_24H_DEC,
        description=f"24h VIP Pass: Micro ({settings.PRICE_VIP_24H_DEC} USDC / {settings.VIP_PASS_MAX_CALLS} calls) or Pro ({settings.PRO_PASS_PRICE_DEC} USDC / {settings.PRO_PASS_MAX_CALLS} calls)",
        resource_url=str(request.url),
    )


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
                    "is_stale": False,
                    "is_synthetic": False,
                }
            ],
            "summary": "Tracking Base L2 liquidity pools (Schema Template).",
            "meta": {
                "sources": ["schema_template"],
                "as_of": "2026-01-01T00:00:00Z",
                "data_age_seconds": 0,
                "is_stale": False,
                "fallback_reason": None,
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

    radar = await fetch_base_dex_radar()
    radar_meta = radar.get("meta", {})
    radar_age = radar_meta.get("data_age_seconds")
    if (
        radar.get("source_status") in ("static_seed", "fallback_resilient_feed")
        or (radar_meta.get("is_stale") and radar_age is not None and radar_age > PAID_MAX_STALE_AGE_SECONDS)
    ):
        return JSONResponse(
            status_code=503,
            content={
                "status": "DATA_QUALITY_UNAVAILABLE",
                "error": (
                    "Upstream DEX feed is degraded. Paid live data is withheld rather than "
                    "selling hardcoded seed values. No payment was requested or charged."
                ),
                "retry_after_seconds": 60,
                "feed": "/api/v1/base-dex-radar",
                "meta": {
                    "source": radar.get("source_status"),
                    "fallback_reason": radar_meta.get("fallback_reason"),
                    "sample_url": "/api/v1/base-dex-radar?sample=true",
                },
            },
            headers={"Retry-After": "60"},
        )

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

    return {k: v for k, v in radar.items() if k != "_observed_ts"}


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

    trending_feed = await fetch_trending_dex_tokens()
    canonical_match = next(
        (t for t in trending_feed.get("tokens", []) if t["slug"] == clean_slug),
        None,
    )

    if canonical_match:
        matched = {
            "slug": canonical_match["slug"],
            "asset_name": canonical_match.get("asset_name") or canonical_match.get("name") or canonical_match["slug"].capitalize(),
            "asset_symbol": canonical_match.get("asset_symbol") or canonical_match.get("symbol") or canonical_match["slug"].upper(),
            "coingecko_id": canonical_match["slug"],
            "price_usdc": canonical_match.get("price_usdc", float(settings.PRICE_DYNAMIC_DEC)),
        }
    else:
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
        if canonical_match:
            sample_payload = {
                "timestamp": "2026-01-01T00:00:00Z",
                "tier": "dynamic_trending_0.05_usdc",
                "source_status": "SCHEMA_TEMPLATE_PREVIEW",
                "asset": {
                    "slug": clean_slug,
                    "name": canonical_match["asset_name"],
                    "symbol": canonical_match["asset_symbol"],
                    "liquidity_usd": 0.0,
                    "volume_24h_usd": 0.0,
                    "momentum_24h_pct": 0.0,
                    "dex": "Aerodrome / Base",
                    "liquidity_class": "DEEP_LIQUIDITY",
                    "pool_age_days": None,
                    "is_stale": False,
                    "is_synthetic": False,
                },
                "meta": {
                    "source": "schema_template",
                    "as_of": "2026-01-01T00:00:00Z",
                    "data_age_seconds": 0,
                    "is_stale": False,
                    "fallback_reason": None,
                    "disclaimer": "Informational quantitative market data only. Not financial, trading, or investment advice.",
                },
                "cache_hit": False,
            }
        else:
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
                    "is_stale": False,
                    "is_synthetic": False,
                },
                "meta": {
                    "sources": ["schema_template"],
                    "as_of": "2026-01-01T00:00:00Z",
                    "data_age_seconds": 0,
                    "is_stale": False,
                    "fallback_reason": None,
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

    dynamic_pulse = None
    if canonical_match:
        token_age = (
            canonical_match.get("data_age_seconds")
            if canonical_match.get("data_age_seconds") is not None
            else trending_feed.get("data_age_seconds")
        )
        if (
            trending_feed.get("source") == "static_seed"
            or canonical_match.get("is_synthetic")
            or (canonical_match.get("is_stale") and token_age is not None and token_age > PAID_MAX_STALE_AGE_SECONDS)
        ):
            # Y2/Z2/Z3/AA2: never sell hardcoded seed values or expired stale data. Report outage and charge nothing.
            return JSONResponse(
                status_code=503,
                content={
                    "status": "DATA_QUALITY_UNAVAILABLE",
                    "error": (
                        "Upstream DEX feed is degraded. Paid live data is withheld rather than "
                        "selling hardcoded seed values. No payment was requested or charged."
                    ),
                    "retry_after_seconds": 60,
                    "feed": f"/api/v1/trending/{clean_slug}",
                    "meta": {
                        "source": trending_feed.get("source"),
                        "fallback_reason": trending_feed.get("fallback_reason"),
                        "free_feed": "/api/v1/trending",
                        "sample_url": f"/api/v1/trending/{clean_slug}?sample=true",
                    },
                },
                headers={"Retry-After": "60"},
            )
    else:
        dynamic_pulse = await fetch_dynamic_asset_pulse(
            slug=clean_slug,
            asset_name=matched["asset_name"],
            asset_symbol=matched["asset_symbol"],
            coingecko_id=matched["coingecko_id"],
        )
        dyn_meta = dynamic_pulse.get("meta", {})
        dyn_age = dyn_meta.get("data_age_seconds")
        if (
            dynamic_pulse.get("source_status") in ("static_seed", "fallback_resilient_feed")
            or dynamic_pulse.get("asset", {}).get("is_synthetic")
            or (dyn_meta.get("is_stale") and dyn_age is not None and dyn_age > PAID_MAX_STALE_AGE_SECONDS)
        ):
            return JSONResponse(
                status_code=503,
                content={
                    "status": "DATA_QUALITY_UNAVAILABLE",
                    "error": (
                        "Upstream market feed is degraded. Paid live data is withheld rather than "
                        "selling hardcoded seed values. No payment was requested or charged."
                    ),
                    "retry_after_seconds": 60,
                    "feed": f"/api/v1/trending/{clean_slug}",
                    "meta": {
                        "source": dynamic_pulse.get("source_status"),
                        "fallback_reason": dyn_meta.get("fallback_reason"),
                        "free_feed": "/api/v1/trending",
                        "sample_url": f"/api/v1/trending/{clean_slug}?sample=true",
                    },
                },
                headers={"Retry-After": "60"},
            )

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
    if canonical_match:
        token_as_of = canonical_match.get("data_as_of") or trending_feed.get("data_as_of")
        token_age = (
            canonical_match.get("data_age_seconds")
            if canonical_match.get("data_age_seconds") is not None
            else trending_feed.get("data_age_seconds")
        )
        return {
            "status": "ok",
            "tier": "dynamic_trending_0.05_usdc",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "asset": {
                "slug": clean_slug,
                "name": canonical_match["asset_name"],
                "symbol": canonical_match["asset_symbol"],
                "liquidity_usd": canonical_match.get("liquidity_usd", 0.0),
                "volume_24h_usd": canonical_match.get("volume_24h_usd", 0.0),
                "momentum_24h_pct": canonical_match.get("momentum_24h_pct", 0.0),
                "dex": canonical_match.get("dex", "Aerodrome / Base"),
                "liquidity_class": canonical_match.get("liquidity_class", "DEEP_LIQUIDITY"),
                "pool_age_days": canonical_match.get("pool_age_days"),
                "is_stale": bool(canonical_match.get("is_stale", False)),
                "is_synthetic": bool(canonical_match.get("is_synthetic", False)),
            },
            "meta": {
                "source": trending_feed.get("source", "dexscreener_base_live"),
                "as_of": token_as_of,
                "data_age_seconds": token_age,
                "is_stale": bool(canonical_match.get("is_stale", False)),
                "fallback_reason": trending_feed.get("fallback_reason"),
                "disclaimer": "Informational quantitative market data only. Not financial, trading, or investment advice.",
            },
        }
    return {k: v for k, v in dynamic_pulse.items() if k != "_observed_ts"}


@router.api_route(
    "/arb-scanner",
    methods=["GET", "HEAD"],
    openapi_extra={
        "x-payment-protocol": "x402",
        "x-payment-network": "base-mainnet",
        "x-payment-chain-id": 8453,
        "x-payment-token": "USDC",
        "x-payment-token-contract": settings.USDC_CONTRACT_ADDRESS,
        "x-payment-recipient": settings.WALLET_ADDRESS,
        "x-payment-price-usdc": settings.PRICE_MICRO_USDC,
        "x-sample-url": "/api/v1/arb-scanner?sample=true",
    },
)
async def get_arb_scanner(request: Request):
    """
    Base L2 Real-time Arbitrage, Spread & Momentum Scanner ($0.005 USDC):
    Delivers cross-asset ratios (ETH/BTC, SOL/ETH), spread efficiency, and Base L2 gas benchmarks.
    Append ?sample=true for a free schema verification sample.
    """
    if _is_sample_request(request):
        if request.method == "HEAD":
            return Response(status_code=200, media_type="application/json")
        sample_payload = {
            "timestamp": "2026-01-01T00:00:00Z",
            "service": "arb-scanner",
            "tier": "micro_0.005_usdc",
            "benchmark_prices": {"BTC": 85000.0, "ETH": 3200.0, "SOL": 180.0},
            "arbitrage_ratios": [
                {"pair": "ETH/BTC", "ratio": 0.037647, "momentum_1h": "steady", "spread_efficiency_pct": 99.85},
                {"pair": "SOL/ETH", "ratio": 0.05625, "momentum_1h": "expanding", "spread_efficiency_pct": 99.72},
            ],
            "base_l2_gas_gwei": 0.005,
            "meta": {"status": "SCHEMA_SAMPLE_ONLY", "disclaimer": "Structure template only. Live data requires 0.005 USDC."},
        }
        return {
            "status": "SAMPLE_DATA_VERIFIED",
            "sample_mode": True,
            "feed": "/api/v1/arb-scanner",
            "live_price_usdc": settings.PRICE_MICRO_USDC,
            "payload": sample_payload,
        }

    db_override = request.app.state.db_path if hasattr(request.app.state, "db_path") else None
    payment_check = await require_x402_payment(
        request=request,
        price_usdc=settings.PRICE_MICRO_DEC,
        description="Base L2 Real-time Arbitrage, Spread & Momentum Scanner (JSON)",
        tier="micro",
        db_path=db_override,
    )
    if payment_check:
        return payment_check

    return await fetch_arb_scanner_data()


@router.api_route(
    "/sentiment-signals",
    methods=["GET", "HEAD"],
    openapi_extra={
        "x-payment-protocol": "x402",
        "x-payment-network": "base-mainnet",
        "x-payment-chain-id": 8453,
        "x-payment-token": "USDC",
        "x-payment-token-contract": settings.USDC_CONTRACT_ADDRESS,
        "x-payment-recipient": settings.WALLET_ADDRESS,
        "x-payment-price-usdc": settings.PRICE_DEX_RADAR_USDC,
        "x-sample-url": "/api/v1/sentiment-signals?sample=true",
    },
)
async def get_sentiment_signals(request: Request):
    """
    Multi-Source Quantitative Sentiment & Action Signals ($0.020 USDC):
    Delivers structured quantitative trading signals (regime, primary signal, confidence score, and key drivers).
    Append ?sample=true for a free schema verification sample.
    """
    if _is_sample_request(request):
        if request.method == "HEAD":
            return Response(status_code=200, media_type="application/json")
        sample_payload = {
            "timestamp": "2026-01-01T00:00:00Z",
            "service": "sentiment-signals",
            "tier": "micro_0.02_usdc",
            "regime": "bullish_expansion",
            "primary_signal": "CAUTION_OVERBOUGHT",
            "confidence": 0.72,
            "fear_and_greed": {"value": 74, "classification": "Greed"},
            "volatility_regime": "MODERATE",
            "key_drivers": ["Fear & Greed Index elevated", "Parkinson aggregate volatility at 2.4%"],
            "meta": {"status": "SCHEMA_SAMPLE_ONLY"},
        }
        return {
            "status": "SAMPLE_DATA_VERIFIED",
            "sample_mode": True,
            "feed": "/api/v1/sentiment-signals",
            "live_price_usdc": settings.PRICE_DEX_RADAR_USDC,
            "payload": sample_payload,
        }

    db_override = request.app.state.db_path if hasattr(request.app.state, "db_path") else None
    payment_check = await require_x402_payment(
        request=request,
        price_usdc=settings.PRICE_DEX_RADAR_DEC,
        description="Multi-Source Quantitative Sentiment & Action Signals (JSON)",
        tier="micro",
        db_path=db_override,
    )
    if payment_check:
        return payment_check

    return await fetch_sentiment_signals()


@router.api_route(
    "/multi-source-dossier",
    methods=["GET", "HEAD"],
    openapi_extra={
        "x-payment-protocol": "x402",
        "x-payment-network": "base-mainnet",
        "x-payment-chain-id": 8453,
        "x-payment-token": "USDC",
        "x-payment-token-contract": settings.USDC_CONTRACT_ADDRESS,
        "x-payment-recipient": settings.WALLET_ADDRESS,
        "x-payment-price-usdc": settings.PRICE_PREMIUM_USDC,
        "x-sample-url": "/api/v1/multi-source-dossier?sample=true",
    },
)
async def get_multi_source_dossier(request: Request):
    """
    Comprehensive Multi-Source Intelligence Dossier ($0.150 USDC):
    Delivers multi-source spot data, Base liquidity metrics, sentiment, and actionable trading directives.
    Append ?sample=true for a free schema verification sample.
    """
    if _is_sample_request(request):
        if request.method == "HEAD":
            return Response(status_code=200, media_type="application/json")
        sample_payload = {
            "timestamp": "2026-01-01T00:00:00Z",
            "service": "multi-source-dossier",
            "tier": "premium_0.15_usdc",
            "dossier_summary": {
                "executive_verdict": "NEUTRAL_ACCUMULATION",
                "risk_score_10": 4.5,
                "liquidity_depth_score_10": 8.2,
                "actionable_bot_directives": ["Execute Base L2 spot swaps within <0.2% slippage"],
            },
            "meta": {"status": "SCHEMA_SAMPLE_ONLY"},
        }
        return {
            "status": "SAMPLE_DATA_VERIFIED",
            "sample_mode": True,
            "feed": "/api/v1/multi-source-dossier",
            "live_price_usdc": settings.PRICE_PREMIUM_USDC,
            "payload": sample_payload,
        }

    db_override = request.app.state.db_path if hasattr(request.app.state, "db_path") else None
    payment_check = await require_x402_payment(
        request=request,
        price_usdc=settings.PRICE_PREMIUM_DEC,
        description="Comprehensive Multi-Source Quantitative Intelligence Dossier (JSON)",
        tier="premium",
        db_path=db_override,
    )
    if payment_check:
        return payment_check

    return await fetch_multi_source_dossier()


@router.api_route(
    "/quality/{slug}",
    methods=["GET", "HEAD"],
    openapi_extra={
        "x-payment-protocol": "x402",
        "x-payment-network": "base-mainnet",
        "x-payment-chain-id": 8453,
        "x-payment-token": "USDC",
        "x-payment-token-contract": settings.USDC_CONTRACT_ADDRESS,
        "x-payment-recipient": settings.WALLET_ADDRESS,
        "x-payment-price-usdc": settings.PRICE_QUALITY_USDC,
        "x-sample-url": "/api/v1/quality/btc?sample=true",
    },
)
async def get_data_quality_audit(slug: str, request: Request):
    """
    Data Quality, Staleness & Integrity Audit per Asset ($0.002 USDC):
    Delivers verifiable data age, upstream status, fallback flags, and consensus health.
    Append ?sample=true for a free schema verification sample.
    """
    if _is_sample_request(request):
        if request.method == "HEAD":
            return Response(status_code=200, media_type="application/json")
        sample_payload = {
            "timestamp": "2026-01-01T00:00:00Z",
            "service": "data-quality-audit",
            "target_slug": slug.lower(),
            "tier": "micro_0.002_usdc",
            "quality_score": 98.5,
            "is_stale": False,
            "data_age_seconds": 12,
            "as_of": "2026-01-01T00:00:00Z",
            "source_status": "SCHEMA_SAMPLE_ONLY",
            "fallback_reason": None,
            "node_consensus_healthy": True,
        }
        return {
            "status": "SAMPLE_DATA_VERIFIED",
            "sample_mode": True,
            "feed": f"/api/v1/quality/{slug}",
            "live_price_usdc": settings.PRICE_QUALITY_USDC,
            "payload": sample_payload,
        }

    db_override = request.app.state.db_path if hasattr(request.app.state, "db_path") else None
    payment_check = await require_x402_payment(
        request=request,
        price_usdc=settings.PRICE_QUALITY_DEC,
        description=f"Independent Data Quality & Integrity Audit for {slug.upper()} (JSON)",
        tier="micro",
        db_path=db_override,
    )
    if payment_check:
        return payment_check

    return await fetch_data_quality(slug)
