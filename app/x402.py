"""
x402 Payment Protocol Middleware & On-Chain Base L2 USDC Verifier.
Implements:
- HTTP 402 Payment Required JSON response (x402 v1.0 specification)
- Replay attack prevention via SQLite used_transactions table
- Real on-chain verification against Base Mainnet RPC (ERC-20 Transfer log inspection for USDC)
- Hybrid test mode support (allows simulated `test_tx_<unique>` proofs for local/CI verification)
"""

import re
from typing import Any, Dict, Optional, Tuple
import httpx
from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse

from app.config import settings
from app.database import get_stats, is_tx_used, record_paid_call

# Keccak-256 topic0 for ERC-20 Transfer(address indexed from, address indexed to, uint256 value)
ERC20_TRANSFER_TOPIC = (
    "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"
)
USDC_DECIMALS = 6
TX_HASH_REGEX = re.compile(r"^0x[a-fA-F0-9]{64}$")


def build_402_response(
    price_usdc: float,
    description: str,
    error_message: str = "Payment Required",
    status_code: int = 402,
) -> JSONResponse:
    """Build standard x402 v1.0 machine-readable payment requirement response."""
    return JSONResponse(
        status_code=status_code,
        headers={
            "X-Payment-Version": "x402/1.0",
            "X-Payment-Network": "base-mainnet",
            "X-Payment-Token": "USDC",
            "X-Payment-Amount": f"{price_usdc:.2f}",
            "X-Payment-Recipient": settings.WALLET_ADDRESS,
        },
        content={
            "error": error_message,
            "x402_version": "1.0",
            "payment_details": {
                "network": "base-mainnet",
                "chain_id": 8453,
                "token": "USDC",
                "token_contract": settings.USDC_CONTRACT_ADDRESS,
                "amount": f"{price_usdc:.2f}",
                "recipient": settings.WALLET_ADDRESS,
                "description": description,
            },
            "instructions": (
                "Sign USDC transfer on Base (Chain ID 8453) to recipient address "
                "and retry request with transaction hash in X-PAYMENT-PROOF header."
            ),
        },
    )


async def verify_base_usdc_transaction(
    tx_hash: str,
    expected_amount_usdc: float,
    recipient_wallet: Optional[str] = None,
    rpc_url: Optional[str] = None,
) -> Tuple[bool, str, str]:
    """
    Verify an on-chain Base Mainnet transaction receipt via JSON-RPC:
    1. Confirms transaction status == 0x1 (succeeded)
    2. Inspects ERC-20 Transfer logs from the official Base USDC contract
    3. Confirms recipient matches John's wallet and transferred amount >= expected_amount_usdc

    Returns:
        (is_valid, payer_address, reason)
    """
    target_wallet = (recipient_wallet or settings.WALLET_ADDRESS).lower()
    usdc_contract = settings.USDC_CONTRACT_ADDRESS.lower()
    endpoint_rpc = rpc_url or settings.BASE_RPC_URL

    if not TX_HASH_REGEX.match(tx_hash.strip()):
        return False, "", "Invalid transaction hash format (expected 0x + 64 hex chars)."

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
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.post(candidate_url, json=payload)
                resp.raise_for_status()
                data = resp.json()
                if data and "result" in data:
                    break
        except Exception as exc:
            last_err = exc
            continue

    if data is None:
        return False, "", f"Base RPC communication error: {last_err}"

    receipt = data.get("result")
    if not receipt:
        return False, "", "Transaction receipt not found on Base Mainnet."

    if receipt.get("status") != "0x1":
        return False, "", "Transaction failed or reverted on-chain."

    expected_units = int(round(expected_amount_usdc * (10**USDC_DECIMALS)))
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


async def require_x402_payment(
    request: Request,
    price_usdc: float,
    description: str,
    tier: str = "micro",
    db_path: Optional[str] = None,
) -> Optional[JSONResponse]:
    """
    Validate x402 payment on incoming M2M API request.
    - If system is paused (Emergency Stop), raises HTTP 503.
    - If X-PAYMENT-PROOF header is missing, returns HTTP 402 JSONResponse.
    - If X-PAYMENT-PROOF was already used (Replay attack), returns HTTP 402/409 JSONResponse.
    - Verifies proof (hybrid simulated proof or live Base RPC receipt) and records revenue.
    - Returns None when payment is valid and recorded.
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

    # Check Replay Protection
    if is_tx_used(payment_proof, db_path):
        return build_402_response(
            price_usdc,
            description,
            error_message="Payment proof transaction hash has already been used (Replay rejected).",
            status_code=402,
        )

    verify_mode = settings.X402_VERIFY_MODE.lower()
    payer_address = "0x_bot_client"
    verified_label = "onchain"

    # Hybrid mode allows deterministic test tokens (`test_tx_...`) for instant sandbox/unit testing
    if verify_mode == "hybrid" and payment_proof.lower().startswith("test_tx_"):
        if len(payment_proof) < 12:
            return build_402_response(
                price_usdc,
                description,
                error_message="Invalid test payment proof token.",
            )
        verified_label = "hybrid_sandbox"
    else:
        is_valid, payer, reason = await verify_base_usdc_transaction(
            tx_hash=payment_proof,
            expected_amount_usdc=price_usdc,
        )
        if not is_valid:
            return build_402_response(
                price_usdc,
                description,
                error_message=f"Payment verification failed: {reason}",
            )
        payer_address = payer

    # Record valid payment & increment stats
    record_paid_call(
        tx_hash=payment_proof,
        endpoint=request.url.path,
        amount_usdc=price_usdc,
        tier=tier,
        payer_address=payer_address,
        verified_mode=verified_label,
        db_path=db_path,
    )
    return None

