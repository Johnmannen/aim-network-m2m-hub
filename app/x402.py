"""
x402 Payment Protocol Middleware & On-Chain Base L2 USDC Verifier.
Implements:
- HTTP 402 Payment Required JSON response (x402 v1.0 specification)
- Atomic Replay attack prevention via SQLite used_transactions PRIMARY KEY
- Real on-chain verification against Base Mainnet RPC (ERC-20 Transfer log inspection for USDC)
- Exact integer micro-USDC (6 decimals) math via Decimal (no float rounding bugs)
- Shared httpx.AsyncClient reuse when available on app.state
"""

import asyncio
import functools
import logging
import re
import time
from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Dict, Literal, Optional, Tuple, overload
import httpx
from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse

from app import x402_standard
from app.config import settings
from app.database import (
    check_and_use_vip_pass,
    create_vip_pass,
    get_stats,
    grant_welcome_bonus_pass,
    is_first_time_buyer,
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


def format_price_str(price_usdc: float | Decimal | str) -> str:
    """Format USDC price string accurately preserving micro-cents (e.g. 0.005, 0.02, 0.15, 1.50)."""
    d = Decimal(str(price_usdc))
    s = f"{d:.4f}".rstrip("0").rstrip(".")
    if "." in s and len(s.split(".")[1]) < 2:
        return f"{d:.2f}"
    return s


def build_402_response(
    price_usdc: float | Decimal,
    description: str,
    error_message: str = "Payment Required",
    status_code: int = 402,
    sample_teaser: Optional[Dict[str, Any]] = None,
    resource_url: str = "",
) -> JSONResponse:
    """Build standard x402 v2.0 machine-readable payment requirement response with live teaser."""
    price_str = format_price_str(price_usdc)
    vip_str = format_price_str(settings.PRICE_VIP_24H_DEC)
    teaser = sample_teaser or {
        "live_feed_verified": True,
        "sla_latency_ms": "<150ms server-side (cached)",
        "unlocked_on_payment": [
            "Real-time BTC/ETH/SOL prices & 24h volumes",
            "Fear & Greed Index + Volatility Index",
            "Base L2 DEX Whale Liquidity & Actionable Signals",
        ],
    }
    v2_payment_req_header = x402_standard.payment_required_header(
        price_usdc, description, resource_url
    )
    headers = {
        "X-Payment-Version": "x402/1.0",
        "X-Payment-Network": "base-mainnet",
        "X-Payment-Token": "USDC",
        "X-Payment-Amount": price_str,
        "X-Payment-Recipient": settings.WALLET_ADDRESS,
    }
    content = {
        "error": error_message,
        "x402_version": "1.0",
        "payment_details": {
            "network": "base-mainnet",
            "chain_id": settings.BASE_CHAIN_ID,
            "token": "USDC",
            "token_contract": settings.USDC_CONTRACT_ADDRESS,
            "amount": price_str,
            "amount_units": str(x402_standard.to_units(price_usdc)),
            "recipient": settings.WALLET_ADDRESS,
            "description": description,
            "vip_24h_pass_options": {
                "micro_pass": {
                    "price_usdc": vip_str,
                    "max_calls": settings.VIP_PASS_MAX_CALLS,
                    "scope": "Micro feeds ($0.005-$0.020)",
                    "description": (
                        f"Pay {vip_str} USDC once to unlock a 24-hour Micro VIP Pass "
                        f"({settings.VIP_PASS_MAX_CALLS} calls across micro feeds using the same tx_hash)."
                    ),
                },
                "pro_pass": {
                    "price_usdc": f"{settings.PRO_PASS_PRICE_DEC:.2f}",
                    "max_calls": settings.PRO_PASS_MAX_CALLS,
                    "scope": f"All feeds including Deep Market Report / Multi-Source Dossier (${settings.PRICE_PREMIUM_DEC:.2f})",
                    "description": (
                        f"Pay {settings.PRO_PASS_PRICE_DEC:.2f} USDC once to unlock a 24-hour Pro VIP Pass "
                        f"({settings.PRO_PASS_MAX_CALLS} calls across all feeds using the same tx_hash)."
                    ),
                },
            },
        },
        "free_live_teaser": teaser,
        "instructions": (
            "Standard x402 v2 (recommended): Sign EIP-3009 USDC authorization and send in PAYMENT-SIGNATURE or X-PAYMENT header. "
            "Legacy on-chain: Transfer USDC on Base (Chain ID 8453) to recipient address and retry with transaction hash in X-PAYMENT-PROOF header."
        ),
    }
    if x402_standard.is_enabled():
        content.update(x402_standard.v1_body_fields(price_usdc, description, resource_url))
        headers["PAYMENT-REQUIRED"] = x402_standard.payment_required_header(
            price_usdc, description, resource_url
        )
    return JSONResponse(status_code=status_code, headers=headers, content=content)


@overload
async def verify_base_usdc_transaction(
    tx_hash: str,
    expected_amount_usdc: float | Decimal,
    recipient_wallet: Optional[str] = None,
    rpc_url: Optional[str] = None,
    http_client: Optional[httpx.AsyncClient] = None,
    return_amount: Literal[False] = False,
) -> Tuple[bool, str, str]:
    ...


@overload
async def verify_base_usdc_transaction(
    tx_hash: str,
    expected_amount_usdc: float | Decimal,
    recipient_wallet: Optional[str] = None,
    rpc_url: Optional[str] = None,
    http_client: Optional[httpx.AsyncClient] = None,
    return_amount: Literal[True] = ...,
) -> Tuple[bool, str, str, float]:
    ...


async def verify_base_usdc_transaction(
    tx_hash: str,
    expected_amount_usdc: float | Decimal,
    recipient_wallet: Optional[str] = None,
    rpc_url: Optional[str] = None,
    http_client: Optional[httpx.AsyncClient] = None,
    return_amount: bool = False,
) -> Tuple[bool, str, str] | Tuple[bool, str, str, float]:
    """
    Verify an on-chain Base Mainnet transaction receipt via JSON-RPC:
    1. Confirms transaction status == 0x1 (succeeded)
    2. Inspects ERC-20 Transfer logs from the official Base USDC contract
    3. Confirms recipient matches configured wallet and transferred micro-USDC >= expected_units

    Returns:
        (is_valid, payer_address, reason) or (is_valid, payer_address, reason, actual_amount_usdc)
    """
    def _fail(reason: str):
        if return_amount:
            return False, "", reason, 0.0
        return False, "", reason

    target_wallet = (recipient_wallet or settings.WALLET_ADDRESS).lower()
    usdc_contract = settings.USDC_CONTRACT_ADDRESS.lower()
    endpoint_rpc = rpc_url or settings.BASE_RPC_URL

    if not TX_HASH_REGEX.match(tx_hash.strip()):
        return _fail("Invalid transaction hash format (expected 0x + 64 hex chars).")

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
        return _fail(f"Base RPC communication error: {last_err}")

    receipt = data.get("result")
    if not receipt:
        return _fail("Transaction receipt not found on Base Mainnet.")

    if receipt.get("status") != "0x1":
        return _fail("Transaction failed or reverted on-chain.")

    min_conf = int(getattr(settings, "MIN_CONFIRMATIONS", 1))
    if min_conf > 1:
        raw_tx_block = receipt.get("blockNumber")
        if not raw_tx_block:
            return _fail(
                f"Transaction is still pending / missing blockNumber (requires >= {min_conf} confirmations)."
            )
        tx_block = int(raw_tx_block, 16)
        block_payload = {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "eth_blockNumber",
            "params": [],
        }
        try:
            if http_client is not None:
                b_resp = await http_client.post(
                    endpoint_rpc, json=block_payload, timeout=5.0
                )
            else:
                async with httpx.AsyncClient(timeout=5.0) as client:
                    b_resp = await client.post(endpoint_rpc, json=block_payload)
            b_resp.raise_for_status()
            b_data = b_resp.json()
            if not b_data or not b_data.get("result"):
                return _fail("Unable to verify block confirmations (empty eth_blockNumber response).")
            latest_block = int(b_data["result"], 16)
            confirmations = max(0, latest_block - tx_block + 1)
            if confirmations < min_conf:
                return _fail(f"Insufficient block confirmations ({confirmations}/{min_conf}).")
        except Exception as exc:
            logger.warning("Block confirmation check failed (fail-closed): %s", exc)
            return _fail(f"Unable to verify block confirmations via RPC: {exc}")

    # P2: Check transaction freshness (prevent historical transfer scraping)
    max_tx_age_seconds = int(getattr(settings, "MAX_TX_AGE_SECONDS", 900))
    raw_tx_block = receipt.get("blockNumber")
    if raw_tx_block and max_tx_age_seconds > 0:
        try:
            block_call = {
                "jsonrpc": "2.0",
                "id": 3,
                "method": "eth_getBlockByNumber",
                "params": [raw_tx_block, False],
            }
            if http_client is not None:
                blk_resp = await http_client.post(endpoint_rpc, json=block_call, timeout=5.0)
            else:
                async with httpx.AsyncClient(timeout=5.0) as client:
                    blk_resp = await client.post(endpoint_rpc, json=block_call)
            blk_resp.raise_for_status()
            blk_data = blk_resp.json()
            if blk_data and blk_data.get("result"):
                block_ts = int(blk_data["result"].get("timestamp", "0x0"), 16)
                if block_ts > 0:
                    import time
                    age_seconds = time.time() - block_ts
                    if age_seconds > max_tx_age_seconds:
                        return _fail(
                            f"EXPIRED_TRANSACTION: On-chain transfer is {int(age_seconds)}s old (max allowed: {max_tx_age_seconds}s / 15 mins)."
                        )
        except Exception as exc:
            logger.warning("Block timestamp age check failed: %s", exc)

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
                actual_amount = float(Decimal(transferred_units) / Decimal(1_000_000))
                if return_amount:
                    return True, payer, "Verified on Base Mainnet.", actual_amount
                return True, payer, "Verified on Base Mainnet."

    return _fail(
        f"No matching USDC transfer of >= {expected_amount_usdc} USDC to {target_wallet} found in receipt."
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

    resource_url = str(request.url)
    _quote = functools.partial(build_402_response, resource_url=resource_url)
    payment_proof = request.headers.get("X-PAYMENT-PROOF", "").strip()

    # Standard x402: signed EIP-3009 payload in X-PAYMENT (v1) / PAYMENT-SIGNATURE (v2)
    std_header = (
        request.headers.get("X-PAYMENT") or request.headers.get("PAYMENT-SIGNATURE") or ""
    ).strip()
    if std_header and not payment_proof:
        if not x402_standard.is_enabled():
            return _quote(
                price_usdc,
                description,
                error_message="Standard x402 payments are not enabled on this server.",
            )
        payload = x402_standard.decode_payment_header(std_header)
        if payload is None:
            return _quote(
                price_usdc,
                description,
                error_message="Invalid payment header (expected base64-encoded JSON).",
            )
        ok, tx, payer, network, reason = await x402_standard.verify_and_settle(
            payload,
            price_usdc,
            description,
            resource_url,
            client=getattr(request.app.state, "http_client", None),
        )
        if not ok:
            return _quote(
                price_usdc, description, error_message=f"Payment verification failed: {reason}"
            )
        try:
            record_paid_call(
                tx_hash=tx,
                endpoint=request.url.path,
                amount_usdc=float(Decimal(str(price_usdc))),
                tier=tier,
                payer_address=payer,
                verified_mode="x402_facilitator",
                db_path=db_path,
            )
            if settings.WELCOME_BONUS_ENABLED and is_first_time_buyer(payer, db_path=db_path):
                grant_welcome_bonus_pass(
                    tx_hash=tx,
                    payer_address=payer,
                    bonus_calls=settings.WELCOME_BONUS_CALLS,
                    duration_hours=settings.WELCOME_BONUS_DURATION_HOURS,
                    db_path=db_path,
                )
                request.state.welcome_bonus_unlocked = True
                request.state.bonus_tx_hash = tx
        except ValueError:
            logger.error("Settled x402 tx %s was already recorded; serving anyway.", tx)
        request.state.x402_receipt = x402_standard.encode_receipt(tx, network, payer)
        return None

    if not payment_proof:
        return _quote(price_usdc, description)

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
            return _quote(
                price_usdc,
                description,
                error_message="Invalid test payment proof token.",
            )
        verified_label = "hybrid_sandbox"
        payer_address = f"0x_test_{payment_proof.lower()}"
        if payment_proof.lower().startswith("test_vip_"):
            is_pro_test = payment_proof.lower().startswith(("test_vip_pro_", "test_vip_10"))
            amount = float(settings.PRO_PASS_PRICE_DEC) if is_pro_test else float(settings.PRICE_VIP_24H_DEC)
            tier_label = "pro" if is_pro_test else "micro"
            try:
                created = create_vip_pass(
                    tx_hash=payment_proof,
                    amount_usdc=amount,
                    payer_address=payer_address,
                    tier=tier_label,
                    verified_mode=verified_label,
                    db_path=db_path,
                )
                if tier == "premium" and created.get("amount_usdc", 0.0) < float(
                    settings.PRO_PASS_PRICE_DEC
                ):
                    return _quote(
                        price_usdc,
                        description,
                        error_message=(
                            f"Micro VIP Pass (${float(settings.PRICE_VIP_24H_DEC):.2f}) does not include "
                            f"Premium reports ($1.00). Pro Pass "
                            f"(${float(settings.PRO_PASS_PRICE_DEC):.2f}) required."
                        ),
                    )
                return None
            except ValueError:
                return _quote(
                    price_usdc,
                    description,
                    error_message="VIP pass expired or call quota exhausted.",
                )
    else:
        # Check if caller paid >= $2.00 USDC for a new 24h VIP Pass (Micro, or Pro at the configured price)
        verify_res = await verify_base_usdc_transaction(
            tx_hash=payment_proof,
            expected_amount_usdc=settings.PRICE_VIP_24H_DEC,
            http_client=shared_client,
            return_amount=True,
        )
        is_vip, vip_payer, _, transferred_usdc = verify_res
        if is_vip:
            is_pro = transferred_usdc >= float(settings.PRO_PASS_PRICE_DEC)
            pass_tier = "pro" if is_pro else "micro"
            verified_mode = "onchain_vip_pro" if is_pro else "onchain_vip_micro"
            try:
                created = create_vip_pass(
                    tx_hash=payment_proof,
                    amount_usdc=transferred_usdc,
                    payer_address=vip_payer,
                    tier=pass_tier,
                    verified_mode=verified_mode,
                    db_path=db_path,
                )
                if tier == "premium" and created.get("amount_usdc", 0.0) < float(
                    settings.PRO_PASS_PRICE_DEC
                ):
                    return _quote(
                        price_usdc,
                        description,
                        error_message=(
                            f"Micro VIP Pass (${float(settings.PRICE_VIP_24H_DEC):.2f}) does not include "
                            f"Premium reports ($1.00). Pro Pass "
                            f"(${float(settings.PRO_PASS_PRICE_DEC):.2f}) required."
                        ),
                    )
                return None
            except ValueError:
                return _quote(
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
            return _quote(
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
        if settings.WELCOME_BONUS_ENABLED and is_first_time_buyer(payer_address, db_path=db_path):
            grant_welcome_bonus_pass(
                tx_hash=payment_proof,
                payer_address=payer_address,
                bonus_calls=settings.WELCOME_BONUS_CALLS,
                duration_hours=settings.WELCOME_BONUS_DURATION_HOURS,
                db_path=db_path,
            )
            request.state.welcome_bonus_unlocked = True
            request.state.bonus_tx_hash = payment_proof
    except ValueError:
        return _quote(
            price_usdc,
            description,
            error_message="Payment proof transaction hash has already been used (Replay rejected). Tip: Send 2.00 USDC for a 24h multi-call VIP Pass.",
            status_code=402,
        )

    return None
