"""
Unit tests for Milestone M2: x402 Payment Protocol, On-Chain Verifier & Replay Protection.
"""

from pathlib import Path
import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from app.config import settings
from app.database import get_stats, init_db, set_pause_state
from app.x402 import (
    ERC20_TRANSFER_TOPIC,
    require_x402_payment,
    verify_base_usdc_transaction,
)


def create_test_app(db_path: str) -> FastAPI:
    app = FastAPI()

    @app.get("/api/v1/test-micro")
    async def test_micro_endpoint(request: Request):
        check = await require_x402_payment(
            request=request,
            price_usdc=0.01,
            description="Test micro endpoint",
            tier="micro",
            db_path=db_path,
        )
        if check:
            return check
        return {"ok": True, "tier": "micro"}

    return app


def test_missing_payment_returns_402_spec(tmp_path: Path):
    """Calling protected endpoint without X-PAYMENT-PROOF returns HTTP 402 and x402 v1.0 JSON."""
    db_file = str(tmp_path / "test_m2.db")
    init_db(db_file)
    client = TestClient(create_test_app(db_file))

    resp = client.get("/api/v1/test-micro")
    assert resp.status_code == 402
    data = resp.json()
    assert data["error"] == "Payment Required"
    assert data["x402_version"] == "1.0"
    assert data["payment_details"]["network"] == "base-mainnet"
    assert data["payment_details"]["token"] == "USDC"
    assert data["payment_details"]["amount"] == "0.01"
    assert (
        data["payment_details"]["recipient"].lower()
        == "0x1bbae07abebbb61f611391e02e81ee26b0c47b79"
    )


def test_valid_payment_and_replay_rejection(tmp_path: Path):
    """Valid proof unlocks endpoint and records revenue; reusing same proof is rejected with 402."""
    db_file = str(tmp_path / "test_m2_replay.db")
    init_db(db_file)
    client = TestClient(create_test_app(db_file))

    headers = {"X-PAYMENT-PROOF": "test_tx_valid_0001"}
    resp1 = client.get("/api/v1/test-micro", headers=headers)
    assert resp1.status_code == 200
    assert resp1.json()["ok"] is True

    stats = get_stats(db_file)
    assert stats["calls_micro"] == 1
    assert stats["revenue_usdc"] == 0.01

    # Replay same tx_hash -> must be rejected with 402
    resp2 = client.get("/api/v1/test-micro", headers=headers)
    assert resp2.status_code == 402
    assert "already been used" in resp2.json()["error"]


def test_paused_system_returns_503(tmp_path: Path):
    """When Overseer Emergency Stop is active, API returns HTTP 503."""
    db_file = str(tmp_path / "test_m2_pause.db")
    init_db(db_file)
    set_pause_state(True, db_file)
    client = TestClient(create_test_app(db_file))

    resp = client.get(
        "/api/v1/test-micro", headers={"X-PAYMENT-PROOF": "test_tx_valid_0002"}
    )
    assert resp.status_code == 503
    assert "Paused" in resp.json()["detail"] or "paused" in resp.json()["detail"]


@pytest.mark.anyio
async def test_onchain_base_rpc_receipt_verification(monkeypatch):
    """Verify ERC-20 USDC Transfer log parsing for John's Base wallet address."""
    tx_hash = "0x" + "a" * 64
    recipient_padded = "0x" + settings.WALLET_ADDRESS.lower().replace("0x", "").rjust(
        64, "0"
    )
    payer_padded = "0x" + ("1" * 40).rjust(64, "0")
    # 0.01 USDC = 10,000 units (6 decimals) -> hex 0x2710
    mock_receipt = {
        "jsonrpc": "2.0",
        "id": 1,
        "result": {
            "status": "0x1",
            "logs": [
                {
                    "address": settings.USDC_CONTRACT_ADDRESS,
                    "topics": [ERC20_TRANSFER_TOPIC, payer_padded, recipient_padded],
                    "data": hex(10000),
                }
            ],
        },
    }

    class MockResponse:
        def raise_for_status(self):
            pass

        def json(self):
            return mock_receipt

    async def mock_post(self, url, json):
        return MockResponse()

    monkeypatch.setattr("httpx.AsyncClient.post", mock_post)

    is_valid, payer, reason = await verify_base_usdc_transaction(
        tx_hash=tx_hash, expected_amount_usdc=0.01
    )
    assert is_valid is True
    assert payer == "0x" + "1" * 40
    assert "Verified" in reason

