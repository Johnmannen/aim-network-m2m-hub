"""Standard x402 (EIP-3009 via facilitator) compatibility tests with a mocked facilitator."""

import base64
import json
import time

import pytest
from fastapi.testclient import TestClient

from app import x402_standard
from app.config import settings
from app.database import get_stats
from app.main import create_app

URL = "/api/v1/crypto-pulse"  # 0.01 USDC -> 10000 units
TX = "0x" + "ab" * 32


def _client(tmp_path):
    return TestClient(create_app(str(tmp_path / "x.db")))


def _header(value=10000, to=None, valid_before=None, version=1, nonce="0x" + "11" * 32):
    auth = {
        "from": "0x" + "22" * 20,
        "to": to or settings.WALLET_ADDRESS,
        "value": str(value),
        "validAfter": "0",
        "validBefore": str(valid_before or int(time.time()) + 60),
        "nonce": nonce,
    }
    payload = {
        "x402Version": version,
        "scheme": "exact",
        "network": "base" if version == 1 else "eip155:8453",
        "payload": {"signature": "0x" + "33" * 65, "authorization": auth},
    }
    if version == 2:
        payload["accepted"] = {"scheme": "exact", "network": "eip155:8453"}
    return base64.b64encode(json.dumps(payload).encode()).decode()


@pytest.fixture
def facilitator(monkeypatch):
    monkeypatch.setattr(settings, "X402_FACILITATOR_URL", "http://facilitator.test")
    calls = []
    state = {"verify": {"isValid": True, "payer": "0x" + "22" * 20}, "settle": None, "raise": False}

    async def fake_post(client, path, body):
        calls.append(path)
        if state["raise"]:
            raise RuntimeError("down")
        if path == "/verify":
            return state["verify"]
        return state["settle"] or {
            "success": True,
            "transaction": TX,
            "network": "base",
            "payer": "0x" + "22" * 20,
        }

    monkeypatch.setattr(x402_standard, "facilitator_post", fake_post)
    return calls, state


def test_disabled_by_default_keeps_legacy_402(tmp_path):
    c = _client(tmp_path)
    r = c.get(URL)
    assert r.status_code == 402
    assert "accepts" not in r.json() and "PAYMENT-REQUIRED" not in r.headers
    r2 = c.get(URL, headers={"X-PAYMENT": _header()})
    assert r2.status_code == 402 and "not enabled" in r2.json()["error"]


def test_402_advertises_standard_requirements(tmp_path, facilitator):
    r = _client(tmp_path).get(URL)
    assert r.status_code == 402
    body = r.json()
    assert body["x402Version"] == 1 and "payment_details" in body  # legacy preserved
    acc = body["accepts"][0]
    assert acc["scheme"] == "exact" and acc["network"] == "base"
    assert acc["maxAmountRequired"] == "10000"
    assert acc["payTo"] == settings.WALLET_ADDRESS
    assert acc["asset"] == settings.USDC_CONTRACT_ADDRESS
    assert acc["extra"] == {"name": "USD Coin", "version": "2"}
    assert acc["resource"].endswith(URL)
    v2 = json.loads(base64.b64decode(r.headers["PAYMENT-REQUIRED"]))
    assert v2["x402Version"] == 2
    assert v2["accepts"][0]["network"] == "eip155:8453"
    assert v2["accepts"][0]["amount"] == "10000"


@pytest.mark.parametrize("hdr", ["X-PAYMENT", "PAYMENT-SIGNATURE"])
def test_valid_payment_settles_and_returns_receipt(tmp_path, facilitator, hdr):
    calls, _ = facilitator
    c = _client(tmp_path)
    r = c.get(URL, headers={hdr: _header()})
    assert r.status_code == 200, r.text
    assert calls == ["/verify", "/settle"]
    receipt = json.loads(base64.b64decode(r.headers["X-PAYMENT-RESPONSE"]))
    assert receipt["success"] is True and receipt["transaction"] == TX
    assert get_stats(str(tmp_path / "x.db"))["calls_micro"] == 1


def test_v2_payload_accepted(tmp_path, facilitator):
    r = _client(tmp_path).get(URL, headers={"PAYMENT-SIGNATURE": _header(version=2)})
    assert r.status_code == 200


@pytest.mark.parametrize(
    "kwargs",
    [
        {"value": 9999},
        {"to": "0x" + "99" * 20},
        {"valid_before": int(time.time()) - 5},
        {"nonce": "0x1234"},
    ],
)
def test_bad_authorization_rejected_before_facilitator(tmp_path, facilitator, kwargs):
    calls, _ = facilitator
    r = _client(tmp_path).get(URL, headers={"X-PAYMENT": _header(**kwargs)})
    assert r.status_code == 402
    assert calls == []


def test_garbage_header_rejected(tmp_path, facilitator):
    r = _client(tmp_path).get(URL, headers={"X-PAYMENT": "not-base64-json"})
    assert r.status_code == 402


def test_facilitator_rejection_and_outage_do_not_serve(tmp_path, facilitator):
    _, state = facilitator
    state["verify"] = {"isValid": False, "invalidReason": "insufficient_funds"}
    r = _client(tmp_path).get(URL, headers={"X-PAYMENT": _header()})
    assert r.status_code == 402 and "insufficient_funds" in r.json()["error"]

    state["verify"] = {"isValid": True}
    state["raise"] = True
    r = _client(tmp_path).get(URL, headers={"X-PAYMENT": _header()})
    assert r.status_code == 402 and "nothing was charged" in r.json()["error"]


def test_failed_settlement_does_not_serve(tmp_path, facilitator):
    _, state = facilitator
    state["settle"] = {"success": False, "errorReason": "nonce_used"}
    r = _client(tmp_path).get(URL, headers={"X-PAYMENT": _header()})
    assert r.status_code == 402
    assert get_stats(str(tmp_path / "x.db"))["calls_micro"] == 0


def test_cors_exposes_payment_headers(tmp_path):
    r = _client(tmp_path).options(
        URL,
        headers={
            "Origin": "https://agent.example",
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "x-payment",
        },
    )
    assert r.status_code == 200
    assert "x-payment" in r.headers["access-control-allow-headers"].lower()
