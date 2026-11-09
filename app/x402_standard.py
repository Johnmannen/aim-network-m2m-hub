"""
Standard x402 (Coinbase spec, v1 + v2) support, additive to the legacy tx-hash flow.

- 402 responses additionally carry an ``accepts`` list (v1 body) and a base64
  ``PAYMENT-REQUIRED`` header (v2).
- Clients retry with ``X-PAYMENT`` (v1) or ``PAYMENT-SIGNATURE`` (v2): a base64 JSON
  payload holding a signed EIP-3009 ``transferWithAuthorization``.
- A facilitator (``X402_FACILITATOR_URL``) verifies and settles it; we only serve the
  resource after settlement succeeded. Disabled unless a facilitator URL is configured.
"""

import base64
import binascii
import json
import logging
import re
import time
from decimal import ROUND_HALF_UP, Decimal
from typing import Any, Dict, Optional, Tuple

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

NETWORK_V1 = "base"
NETWORK_V2 = "eip155:8453"
MAX_TIMEOUT_SECONDS = 60
USDC_EIP712 = {"name": "USD Coin", "version": "2"}
HEX_RE = re.compile(r"^0x[0-9a-fA-F]+$")
NONCE_RE = re.compile(r"^0x[0-9a-fA-F]{64}$")


def is_enabled() -> bool:
    """Standard x402 is only advertised/accepted when a facilitator is configured."""
    return bool(settings.X402_FACILITATOR_URL)


def to_units(price_usdc: float | str | Decimal) -> int:
    return int((Decimal(str(price_usdc)) * Decimal(10**6)).quantize(Decimal(1), ROUND_HALF_UP))


def requirements(
    version: int, price_usdc: Any, description: str, resource_url: str
) -> Dict[str, Any]:
    """PaymentRequirements for the given x402 version."""
    units = str(to_units(price_usdc))
    base = {
        "scheme": "exact",
        "payTo": settings.WALLET_ADDRESS,
        "maxTimeoutSeconds": MAX_TIMEOUT_SECONDS,
        "asset": settings.USDC_CONTRACT_ADDRESS,
        "extra": dict(USDC_EIP712),
        "resource": resource_url,
        "description": description,
        "mimeType": "application/json",
        "maxAmountRequired": units,
        "amount": units,
    }
    if version >= 2:
        return {"network": NETWORK_V2, **base}
    return {
        "network": NETWORK_V1,
        **base,
    }


def _b64(obj: Dict[str, Any]) -> str:
    return base64.b64encode(json.dumps(obj, separators=(",", ":")).encode()).decode()


def v1_body_fields(price_usdc: Any, description: str, resource_url: str) -> Dict[str, Any]:
    return {
        "x402Version": 1,
        "accepts": [requirements(1, price_usdc, description, resource_url)],
    }


def payment_required_header(price_usdc: Any, description: str, resource_url: str) -> str:
    """v2 ``PAYMENT-REQUIRED`` header value."""
    return _b64(
        {
            "x402Version": 2,
            "resource": {
                "url": resource_url,
                "description": description,
                "mimeType": "application/json",
            },
            "accepts": [requirements(2, price_usdc, description, resource_url)],
        }
    )


def decode_payment_header(value: str) -> Optional[Dict[str, Any]]:
    try:
        padded = value.strip() + "=" * (-len(value.strip()) % 4)
        raw = base64.b64decode(padded, altchars=b"-_")
        data = json.loads(raw)
        return data if isinstance(data, dict) else None
    except (binascii.Error, ValueError, UnicodeDecodeError):
        return None


def encode_receipt(transaction: str, network: str, payer: str) -> str:
    return _b64(
        {"success": True, "transaction": transaction, "network": network, "payer": payer}
    )


def precheck(payload: Dict[str, Any], price_usdc: Any, now: Optional[float] = None) -> Tuple[bool, str]:
    """Cheap local validation so obviously wrong payments never reach the facilitator."""
    now = now if now is not None else time.time()
    version = int(payload.get("x402Version", 1) or 1)
    inner = payload.get("payload")
    if not isinstance(inner, dict):
        return False, "Missing payload."
    auth = inner.get("authorization")
    signature = inner.get("signature")
    if not isinstance(auth, dict) or not isinstance(signature, str) or not HEX_RE.match(signature):
        return False, "Missing or malformed authorization/signature."

    accepted = payload.get("accepted") if version >= 2 else payload
    if not isinstance(accepted, dict):
        accepted = {}
    scheme = accepted.get("scheme", payload.get("scheme"))
    network = accepted.get("network", payload.get("network"))
    if scheme != "exact":
        return False, "Unsupported scheme (expected 'exact')."
    if network not in (NETWORK_V1, NETWORK_V2):
        return False, "Unsupported network (expected Base mainnet)."

    try:
        value = int(str(auth.get("value")))
        valid_after = int(str(auth.get("validAfter", 0)))
        valid_before = int(str(auth.get("validBefore")))
    except (TypeError, ValueError):
        return False, "Malformed authorization numbers."
    if str(auth.get("to", "")).lower() != settings.WALLET_ADDRESS.lower():
        return False, "Authorization recipient does not match payTo."
    if value < to_units(price_usdc):
        return False, "Authorized amount is below the required price."
    if valid_after > now:
        return False, "Authorization not yet valid."
    if valid_before <= now + 5:
        return False, "Authorization expired or expires too soon."
    if not NONCE_RE.match(str(auth.get("nonce", ""))):
        return False, "Malformed nonce."
    return True, "ok"


async def facilitator_post(
    client: Optional[httpx.AsyncClient], path: str, body: Dict[str, Any]
) -> Dict[str, Any]:
    url = settings.X402_FACILITATOR_URL.rstrip("/") + path
    headers = {"Content-Type": "application/json"}
    if settings.X402_FACILITATOR_AUTH:
        headers["Authorization"] = settings.X402_FACILITATOR_AUTH

    async def _do(c: httpx.AsyncClient) -> Dict[str, Any]:
        resp = await c.post(url, json=body, headers=headers, timeout=25.0)
        if resp.status_code >= 500:
            resp.raise_for_status()
        try:
            data = resp.json()
        except ValueError:
            data = {}
        return data if isinstance(data, dict) else {}

    if client is not None:
        return await _do(client)
    async with httpx.AsyncClient() as own:
        return await _do(own)


async def verify_and_settle(
    payload: Dict[str, Any],
    price_usdc: Any,
    description: str,
    resource_url: str,
    client: Optional[httpx.AsyncClient] = None,
) -> Tuple[bool, str, str, str, str]:
    """Returns (ok, transaction, payer, network, reason)."""
    ok, reason = precheck(payload, price_usdc)
    if not ok:
        return False, "", "", "", reason

    version = int(payload.get("x402Version", 1) or 1)
    body = {
        "x402Version": version,
        "paymentPayload": payload,
        "paymentRequirements": requirements(version, price_usdc, description, resource_url),
    }
    try:
        verified = await facilitator_post(client, "/verify", body)
        if not verified.get("isValid"):
            return False, "", "", "", f"Facilitator rejected payment: {verified.get('invalidReason') or 'invalid'}"
        settled = await facilitator_post(client, "/settle", body)
    except Exception as exc:  # network / 5xx
        logger.warning("x402 facilitator error: %s", exc)
        return False, "", "", "", "Facilitator unavailable, nothing was charged. Retry shortly."

    if not settled.get("success") or not settled.get("transaction"):
        return False, "", "", "", f"Settlement failed: {settled.get('errorReason') or 'unknown'}"
    return (
        True,
        str(settled["transaction"]),
        str(settled.get("payer") or verified.get("payer") or ""),
        str(settled.get("network") or (NETWORK_V2 if version >= 2 else NETWORK_V1)),
        "settled",
    )
