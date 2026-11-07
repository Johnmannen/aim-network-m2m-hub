"""
x402 Payment Protocol Middleware & On-Chain Base L2 USDC Verifier.
Implements:
- HTTP 402 Payment Required JSON response (x402 v1.0 specification)
- Atomic Replay attack prevention via SQLite used_transactions PRIMARY KEY
- Real on-chain verification against Base Mainnet RPC (ERC-20 Transfer log inspection for USDC)
- Exact integer micro-USDC (6 decimals) math via Decimal (no float rounding bugs)
- Shared httpx.AsyncClient reuse when available on app.state
"""

import logging
import re
from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Dict, Optional, Tuple
import httpx
from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse

from app.config import settings
from app.database import (
    check_and_use_vip_pass,
    create_vip_pass,
    get_stats,
    record_paid_call,
)

logger = logging.getLogger(__name__)

# Keccak-256 topic0 for ERC-20 Transfer(address indexed from, address indexed to, uint256 value)
ERC20_TRANSFER_TOPIC = (
    "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"
)
USDC_DECIMALS = 6
MICRO_USDC_FACTOR = Decimal("1000000")
TX_HASH_REGEX = re.compile(r"^0x[a-fA-F0-9]{64}$")


def to_micro_usdc(amount_usdc: float | str | Decimal) -> int:
    """Convert a USDC amount to exact integer micro-USDC units (10^6) using Decimal."""
    dec_val = Decimal(str(amount_usdc))
    return int(
        (dec_val * MICRO_USDC_FACTOR).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    )


def build_402_response(
    price_usdc: float | Decimal,
    description: str,
    error_message: str = "Payment Required",
    status_code: int = 402,
    sample_teaser: Optional[Dict[str, Any]] = None,
) -> JSONResponse:
    """Build standard x402 v1.0 machine-readable payment requirement response with live teaser."""
    price_str = f"{Decimal(str(price_usdc)):.2f}"
    vip_str = f"{settings.PRICE_VIP_24H_DEC:.2f}"
    teaser = sample_teaser or {
        "live_feed_verified": True,
        "sla_latency_ms": "<150ms",
        "unlocked_on_payment": [
            "Real-time BTC/ETH/SOL prices & 24h volumes",
            "Fear & Greed Index + Volatility Index",
            "Base L2 DEX Whale Liquidity & Actionable Signals",
        ],
    }
    return JSONResponse(
        status_code=status_code,
        headers={
            "X-Payment-Version": "x402/1.0",
            "X-Payment-Network": "base-mainnet",
            "X-Payment-Token": "USDC",
            "X-Payment-Amount": price_str,
            "X-Payment-Recipient": settings.WALLET_ADDRESS,
        },
        content={
            "error": error_message,
            "x402_version": "1.0",
            "payment_details": {
                "network": "base-mainnet",
                "chain_id": settings.BASE_CHAIN_ID,
                "token": "USDC",
                "token_contract": settings.USDC_CONTRACT_ADDRESS,
                "amount": price_str,
                "recipient": settings.WALLET_ADDRESS,
                "description": description,
                "vip_24h_pass_option": {
                    "amount": vip_str,
                    "description": (
                        f"Pay {vip_str} USDC once to unlock a 24-hour VIP Pass "
                        f"({settings.VIP_PASS_MAX_CALLS} calls across ALL endpoints using the same tx_hash)."
                    ),
                },
            },
            "free_live_teaser": teaser,
            "instructions": (
                "Sign USDC transfer on Base (Chain ID 8453) to recipient address "
                "and retry request with transaction hash in X-PAYMENT-PROOF header."
            ),
        },
    )


async def verify_base_usdc_transaction(
    tx_hash: str,
    expected_amount_usdc: float | Decimal,
    recipient_wallet: Optional[str] = None,
    rpc_url: Optional[str] = None,
    http_client: Optional[httpx.AsyncClient] = None,
) -> Tuple[bool, str, str]:
    """
    Verify an on-chain Base Mainnet transaction receipt via JSON-RPC:
    1. Confirms transaction status == 0x1 (succeeded)
    2. Inspects ERC-20 Transfer logs from the official Base USDC contract
    3. Confirms recipient matches configured wallet and transferred micro-USDC >= expected_units

    Returns:
        (is_valid, payer_address, reason)
    """
    target_wallet = (recipient_wallet or settings.WALLET_ADDRESS).lower()
    usdc_contract = settings.USDC_CONTRACT_ADDRESS.lower()
    endpoint_rpc = rpc_url or settings.BASE_RPC_URL

    if not TX_HASH_REGEX.match(tx_hash.strip()):
        return (
            False,
            "",
            "Invalid transaction hash format (expected 0x + 64 hex chars).",
        )

    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "eth_getTransactionReceipt",
        "params": [tx_hash.strip()],
    }

    rpc_candidates = [endpoint_rpc] + [
        u for u in getattr(settings, "BASE_RPC_FALLBACKS", []) if u != endpoint_rpc
    ]
    data = None
    last_err = None

    for candidate_url in rpc_candidates:
        try:
            if http_client is not None:
                resp = await http_client.post(candidate_url, json=payload, timeout=5.0)
                resp.raise_for_status()
                data = resp.json()
            else:
                async with httpx.AsyncClient(timeout=5.0) as client:
                    resp = await client.post(candidate_url, json=payload)
                    resp.raise_for_status()
                    data = resp.json()
            if data and "result" in data:
                break
        except Exception as exc:
            last_err = exc
            logger.warning("Base RPC candidate %s failed: %s", candidate_url, exc)
            continue

    if data is None:
        return False, "", f"Base RPC communication error: {last_err}"

    receipt = data.get("result")
    if not receipt:
        return False, "", "Transaction receipt not found on Base Mainnet."

    if receipt.get("status") != "0x1":
        return False, "", "Transaction failed or reverted on-chain."

    expected_units = to_micro_usdc(expected_amount_usdc)
    padded_recipient = "0x" + target_wallet.replace("0x", "").rjust(64, "0")

    for log in receipt.get("logs", []):
        log_address = (log.get("address") or "").lower()
        topics = [t.lower() for t in log.get("topics", [])]
        if (
            log_address == usdc_contract
            and len(topics) >= 3
            and topics[0] == ERC20_TRANSFER_TOPIC
            and topics[2] == padded_recipient
        ):
            raw_data = log.get("data", "0x0")
            transferred_units = int(raw_data, 16)
            if transferred_units >= expected_units:
                payer = "0x" + topics[1][-40:]
                return True, payer, "Verified on Base Mainnet."

    return (
        False,
        "",
        f"No matching USDC transfer of >= {expected_amount_usdc} USDC to {target_wallet} found in receipt.",
    )


def _is_test_token_allowed() -> bool:
    """Simulated test_tx_ / test_vip_ proofs are allowed ONLY when BOTH TESTING=True AND mode=='hybrid'."""
    return settings.TESTING and settings.X402_VERIFY_MODE.lower() == "hybrid"


async def require_x402_payment(
    request: Request,
    price_usdc: float | Decimal,
    description: str,
    tier: str = "micro",
    db_path: Optional[str] = None,
) -> Optional[JSONResponse]:
    """
    Validate x402 payment on incoming M2M API request.
    Uses atomic INSERT in SQLite to prevent TOCTOU race condition replay attacks.
    """
    stats = get_stats(db_path)
    if stats["paused"]:
        raise HTTPException(
            status_code=503,
            detail="Service paused by Overseer Emergency Stop.",
        )

    payment_proof = request.headers.get("X-PAYMENT-PROOF", "").strip()
    if not payment_proof:
        return build_402_response(price_usdc, description)

    # 1. Check if payment_proof is an active 24h VIP Pass
    vip_entry = check_and_use_vip_pass(payment_proof, tier=tier, db_path=db_path)
    if vip_entry is not None:
        return None

    payer_address = "0x_bot_client"
    verified_label = "onchain"
    shared_client = getattr(request.app.state, "http_client", None)

    # 2. Verify proof (sandbox test token if allowed, otherwise strict Base RPC verification)
    if _is_test_token_allowed() and payment_proof.lower().startswith(
        ("test_tx_", "test_vip_")
    ):
        if len(payment_proof) < 12:
            return build_402_response(
                price_usdc,
                description,
                error_message="Invalid test payment proof token.",
            )
        verified_label = "hybrid_sandbox"
        if payment_proof.lower().startswith("test_vip_"):
            try:
                create_vip_pass(
                    tx_hash=payment_proof,
                    amount_usdc=float(settings.PRICE_VIP_24H_DEC),
                    payer_address=payer_address,
                    tier="premium",
                    verified_mode=verified_label,
                    db_path=db_path,
                )
                return None
            except ValueError:
                return build_402_response(
                    price_usdc,
                    description,
                    error_message="VIP pass expired or call quota exhausted.",
                )
    else:
        # Check if caller paid >= $2.00 USDC for a new 24h VIP Pass
        is_vip, vip_payer, _ = await verify_base_usdc_transaction(
            tx_hash=payment_proof,
            expected_amount_usdc=settings.PRICE_VIP_24H_DEC,
            http_client=shared_client,
        )
        if is_vip:
            try:
                create_vip_pass(
                    tx_hash=payment_proof,
                    amount_usdc=float(settings.PRICE_VIP_24H_DEC),
                    payer_address=vip_payer,
                    tier="premium",
                    verified_mode="onchain_vip",
                    db_path=db_path,
                )
                return None
            except ValueError:
                return build_402_response(
                    price_usdc,
                    description,
                    error_message="VIP pass expired or call quota exhausted.",
                )

        is_valid, payer, reason = await verify_base_usdc_transaction(
            tx_hash=payment_proof,
            expected_amount_usdc=price_usdc,
            http_client=shared_client,
        )
        if not is_valid:
            return build_402_response(
                price_usdc,
                description,
                error_message=f"Payment verification failed: {reason}",
            )
        payer_address = payer

    # 3. Atomically record single-use transaction (raises ValueError on concurrent replay)
    try:
        record_paid_call(
            tx_hash=payment_proof,
            endpoint=request.url.path,
            amount_usdc=float(Decimal(str(price_usdc))),
            tier=tier,
            payer_address=payer_address,
            verified_mode=verified_label,
            db_path=db_path,
        )
    except ValueError:
        return build_402_response(
            price_usdc,
            description,
            error_message="Payment proof transaction hash has already been used (Replay rejected). Tip: Send 2.00 USDC for a 24h multi-call VIP Pass.",
            status_code=402,
        )

    return None
