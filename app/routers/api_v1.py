"""
M2M Paid API Endpoints (Tier 1: $0.01 USDC & Tier 2: $1.00 USDC).
Protected by x402 Payment Protocol on Base L2.
"""

from fastapi import APIRouter, Request
from app.config import settings
from app.services.market_data import fetch_crypto_pulse_data, fetch_deep_market_report
from app.x402 import require_x402_payment

router = APIRouter(prefix="/api/v1", tags=["M2M Paid Data Endpoints"])


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

