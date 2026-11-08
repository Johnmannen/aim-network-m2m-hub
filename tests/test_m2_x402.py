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


def test_valid_payment_and_replay_rejection(tmp_path: Path, monkeypatch):
    """Valid proof unlocks endpoint and records revenue; reusing same proof is rejected with 402 when bonus disabled."""
    monkeypatch.setattr(settings, "WELCOME_BONUS_ENABLED", False)
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


def test_first_time_buyer_welcome_bonus(tmp_path: Path):
    """Verify first-time buyers get 5 free bonus calls by reusing their original tx_hash."""
    from app.main import create_app
    from fastapi.testclient import TestClient

    db_file = str(tmp_path / "test_welcome_bonus.db")
    app = create_app(db_path=db_file)
    client = TestClient(app)

    # First purchase with a unique test transaction
    tx_first = "test_tx_first_buyer_999"
    r1 = client.get("/api/v1/crypto-pulse", headers={"X-PAYMENT-PROOF": tx_first})
    assert r1.status_code == 200
    assert r1.headers.get("X-Welcome-Bonus") == "5-free-calls-unlocked"
    assert r1.headers.get("X-Bonus-Proof") == tx_first

    # Calls 2 through 6 reuse the same tx_first as bonus calls
    for i in range(5):
        r_bonus = client.get("/api/v1/crypto-pulse", headers={"X-PAYMENT-PROOF": tx_first})
        assert r_bonus.status_code == 200, f"Bonus call {i+1} failed"

    # Call 7 (quota exhausted) -> 402 Payment Required
    r_exhausted = client.get("/api/v1/crypto-pulse", headers={"X-PAYMENT-PROOF": tx_first})
    assert r_exhausted.status_code == 402


@pytest.mark.anyio
async def test_expired_transaction_rejected_by_max_age(monkeypatch):
    """Transactions older than MAX_TX_AGE_SECONDS are rejected with EXPIRED_TRANSACTION."""
    import time
    from app.x402 import verify_base_usdc_transaction

    tx_hash = "0x" + "9" * 64
    block_number = "0x100"
    # Old timestamp: 2 hours ago (> 900 seconds)
    old_timestamp = hex(int(time.time() - 7200))

    mock_receipt = {
        "result": {
            "status": "0x1",
            "blockNumber": block_number,
            "logs": [
                {
                    "address": settings.USDC_CONTRACT_ADDRESS.lower(),
                    "topics": [
                        ERC20_TRANSFER_TOPIC,
                        "0x" + "1" * 64,
                        "0x" + settings.WALLET_ADDRESS.lower().replace("0x", "").rjust(64, "0"),
                    ],
                    "data": hex(10000),
                }
            ],
        }
    }

    mock_block = {
        "result": {
            "timestamp": old_timestamp,
        }
    }

    class MockResponse:
        def __init__(self, data):
            self._data = data

        def raise_for_status(self):
            pass

        def json(self):
            return self._data

    async def mock_post(self, url, json):
        method = json.get("method")
        if method == "eth_getTransactionReceipt":
            return MockResponse(mock_receipt)
        if method == "eth_getBlockByNumber":
            return MockResponse(mock_block)
        return MockResponse({})

    monkeypatch.setattr("httpx.AsyncClient.post", mock_post)

    is_valid, payer, reason = await verify_base_usdc_transaction(
        tx_hash=tx_hash, expected_amount_usdc=0.01
    )
    assert is_valid is False
    assert "EXPIRED_TRANSACTION" in reason


def test_vip_pass_quota_pro_vs_micro(tmp_path: Path):
    """Pro VIP pass (>=10 USDC) gets PRO_PASS_MAX_CALLS, Micro (<10 USDC) gets VIP_PASS_MAX_CALLS."""
    from app.database import create_vip_pass, init_db

    db_file = str(tmp_path / "test_vip_quota.db")
    init_db(db_file)

    micro_pass = create_vip_pass(
        tx_hash="test_vip_micro_tx_001",
        amount_usdc=2.0,
        payer_address="0x_buyer_micro",
        tier="micro",
        db_path=db_file,
    )
    assert micro_pass["max_calls"] == settings.VIP_PASS_MAX_CALLS
    assert micro_pass["amount_usdc"] == 2.0

    pro_pass = create_vip_pass(
        tx_hash="test_vip_pro_tx_002",
        amount_usdc=10.0,
        payer_address="0x_buyer_pro",
        tier="pro",
        db_path=db_file,
    )
    assert pro_pass["max_calls"] == settings.PRO_PASS_MAX_CALLS
    assert pro_pass["amount_usdc"] == 10.0


@pytest.mark.anyio
async def test_verify_base_usdc_with_return_amount(monkeypatch):
    """verify_base_usdc_transaction(return_amount=True) returns actual transferred USDC float."""
    recipient_wallet = "0x89205A3A3b2A69De6Dbf7f01ED13B2108B2c43e7".lower()
    padded_recipient = "0x" + recipient_wallet.replace("0x", "").rjust(64, "0").lower()
    payer_address = "0xde0b295669a9fd93d5f28d9ec85e40f4cb697bae"
    padded_payer = "0x" + payer_address.replace("0x", "").rjust(64, "0").lower()
    tx_hash = "0x" + "a" * 64

    # 10 USDC = 10,000,000 micro-USDC = 0x989680
    mock_receipt = {
        "status": "0x1",
        "blockNumber": "0x100",
        "logs": [
            {
                "address": settings.USDC_CONTRACT_ADDRESS.lower(),
                "topics": [
                    ERC20_TRANSFER_TOPIC,
                    padded_payer,
                    padded_recipient,
                ],
                "data": hex(10_000_000),
            }
        ],
    }

    class MockResponse:
        def __init__(self, data):
            self._data = data

        def raise_for_status(self):
            pass

        def json(self):
            return {"jsonrpc": "2.0", "id": 1, "result": self._data}

    async def mock_post(self, url, json=None, timeout=None):
        method = json.get("method")
        if method == "eth_getTransactionReceipt":
            return MockResponse(mock_receipt)
        if method == "eth_getBlockByNumber":
            return MockResponse({"timestamp": hex(int(time.time()))})
        return MockResponse({})

    monkeypatch.setattr("httpx.AsyncClient.post", mock_post)

    is_valid, payer, reason, amount = await verify_base_usdc_transaction(
        tx_hash=tx_hash,
        expected_amount_usdc=2.00,
        recipient_wallet=recipient_wallet,
        return_amount=True,
    )
    assert is_valid is True
    assert payer == payer_address
    assert amount == 10.0


@pytest.mark.anyio
async def test_require_x402_payment_pro_pass_flow(monkeypatch, tmp_path: Path):
    """A 10 USDC on-chain transfer creates a Pro VIP pass (50 calls) and unlocks premium tier."""
    import time
    from fastapi import Request
    from app.x402 import require_x402_payment
    from app.database import get_vip_pass

    db_file = str(tmp_path / "test_vip_onchain.db")
    recipient_wallet = settings.WALLET_ADDRESS.lower()
    padded_recipient = "0x" + recipient_wallet.replace("0x", "").rjust(64, "0").lower()
    payer_address = "0x1111111111111111111111111111111111111111"
    padded_payer = "0x" + payer_address.replace("0x", "").rjust(64, "0").lower()
    tx_hash = "0x" + "b" * 64

    # 10 USDC = 10,000,000 micro-USDC
    mock_receipt = {
        "status": "0x1",
        "blockNumber": "0x100",
        "logs": [
            {
                "address": settings.USDC_CONTRACT_ADDRESS.lower(),
                "topics": [
                    ERC20_TRANSFER_TOPIC,
                    padded_payer,
                    padded_recipient,
                ],
                "data": hex(10_000_000),
            }
        ],
    }

    class MockResponse:
        def __init__(self, data):
            self._data = data

        def raise_for_status(self):
            pass

        def json(self):
            return {"jsonrpc": "2.0", "id": 1, "result": self._data}

    async def mock_post(self, url, json=None, timeout=None):
        method = json.get("method")
        if method == "eth_getTransactionReceipt":
            return MockResponse(mock_receipt)
        if method == "eth_getBlockByNumber":
            return MockResponse({"timestamp": hex(int(time.time()))})
        return MockResponse({})

    monkeypatch.setattr("httpx.AsyncClient.post", mock_post)

    scope = {
        "type": "http",
        "method": "GET",
        "path": "/api/v1/deep-market-report",
        "headers": [(b"x-payment-proof", tx_hash.encode())],
        "query_string": b"",
        "app": type("App", (), {"state": type("State", (), {"http_client": None, "db_path": db_file})()})(),
    }
    req = Request(scope)

    # Calling premium endpoint ($1.00) with 10 USDC proof -> creates Pro pass and returns None (success!)
    resp = await require_x402_payment(
        request=req,
        price_usdc=1.00,
        description="Deep Market Report",
        tier="premium",
        db_path=db_file,
    )
    assert resp is None

    # Verify Pro pass was stored in SQLite
    pass_record = get_vip_pass(tx_hash, db_path=db_file)
    assert pass_record is not None
    assert pass_record["tier"] == "pro"
    assert pass_record["amount_usdc"] == 10.0
    assert pass_record["max_calls"] == 50
    assert pass_record["calls_used"] == 1



