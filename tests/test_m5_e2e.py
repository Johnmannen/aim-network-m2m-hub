"""
End-to-End (E2E) & Security Audit Test Suite for AIM Network.
Covers:
1. Full E2E system lifecycle (Discovery, Dashboard, x402 Gate, VIP Pass, Telemetry)
2. Persistent PIN brute-force lockout in SQLite (survives in-memory clear/restart)
3. /cron/discover authentication & token separation (SCOUT_SECRET_TOKEN != ADMIN_PIN)
4. Production-mode test-token rejection (TESTING=False blocks test_tx_ even if mode=='hybrid')
5. Concurrent/atomic replay protection on used_transactions
6. Backup snapshot export/import roundtrip & payer_address redaction
7. On-chain block confirmations verification (MIN_CONFIRMATIONS)
"""

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.database import (
    export_db_snapshot,
    get_stats,
    import_db_snapshot,
    init_db,
    record_paid_call,
)
from app.main import create_app
from app.routers.dashboard import _pin_failures
from app.x402 import ERC20_TRANSFER_TOPIC, verify_base_usdc_transaction


def test_full_end_to_end_system(tmp_path: Path):
    db_file = str(tmp_path / "test_e2e_full.db")
    app = create_app(db_path=db_file)

    with TestClient(app) as client:
        # 1. Health & Discovery
        r_health = client.get("/health")
        assert r_health.status_code == 200
        assert (
            r_health.json()["wallet"].lower()
            == "0x1bbae07abebbb61f611391e02e81ee26b0c47b79"
        )

        r_llms = client.get("/llms.txt")
        assert r_llms.status_code == 200
        assert "0x1bbae07abebbb61f611391e02e81ee26b0c47b79" in r_llms.text

        r_agents = client.get("/agents.json")
        assert r_agents.status_code == 200
        assert len(r_agents.json()["endpoints"]) >= 4

        # 2. Dashboard initial render
        client.post("/api/admin/login", json={"pin": settings.ADMIN_PIN})
        r_dash = client.get("/")
        assert r_dash.status_code == 200
        assert "AIM NETWORK — OVERSEER DASHBOARD" in r_dash.text
        assert "ONLINE" in r_dash.text

        # 3. Unpaid requests get HTTP 402 Payment Required
        r_unpaid_micro = client.get("/api/v1/crypto-pulse")
        assert r_unpaid_micro.status_code == 402
        assert r_unpaid_micro.json()["payment_details"]["amount"] == "0.01"

        r_unpaid_prem = client.get("/api/v1/deep-market-report")
        assert r_unpaid_prem.status_code == 402
        assert r_unpaid_prem.json()["payment_details"]["amount"] == "1.00"

        # 4. Paid requests succeed and update SQLite revenue
        r_paid_micro = client.get(
            "/api/v1/crypto-pulse",
            headers={"X-PAYMENT-PROOF": "test_tx_e2e_micro_001"},
        )
        assert r_paid_micro.status_code == 200

        r_paid_prem = client.get(
            "/api/v1/deep-market-report",
            headers={"X-PAYMENT-PROOF": "test_tx_e2e_prem_001"},
        )
        assert r_paid_prem.status_code == 200

        # Replay of used tx_hash is blocked
        r_replay = client.get(
            "/api/v1/crypto-pulse",
            headers={"X-PAYMENT-PROOF": "test_tx_e2e_micro_001"},
        )
        assert r_replay.status_code == 402

        # 5. Check stats via /api/admin/stats & Dashboard HTML
        r_stats = client.get("/api/admin/stats", headers={"X-Admin-Pin": settings.ADMIN_PIN})
        assert r_stats.status_code == 200
        stats_data = r_stats.json()
        assert stats_data["calls_micro"] == 1
        assert stats_data["calls_premium"] == 1
        assert stats_data["revenue_usdc"] == 1.01

        r_dash_after = client.get("/")
        assert "$1.01 USDC" in r_dash_after.text

        # 6. PIN-protected Emergency Stop
        r_bad_pin = client.post("/api/admin/toggle-pause", json={"pin": "wrong-pin"})
        assert r_bad_pin.status_code == 401

        r_pause = client.post(
            "/api/admin/toggle-pause", json={"pin": settings.ADMIN_PIN}
        )
        assert r_pause.status_code == 200
        assert r_pause.json()["paused"] is True

        r_paused_call = client.get(
            "/api/v1/crypto-pulse",
            headers={"X-PAYMENT-PROOF": "test_tx_e2e_while_paused"},
        )
        assert r_paused_call.status_code == 503

        r_resume = client.post(
            "/api/admin/toggle-pause", json={"pin": settings.ADMIN_PIN}
        )
        assert r_resume.status_code == 200
        assert r_resume.json()["paused"] is False

        r_resumed_call = client.get(
            "/api/v1/crypto-pulse",
            headers={"X-PAYMENT-PROOF": "test_tx_e2e_after_resume"},
        )
        assert r_resumed_call.status_code == 200

        # 7. Run Autonomous Scout & verify auto-deployed live endpoint works
        r_scout = client.post("/cron/discover")
        assert r_scout.status_code == 200
        scout_json = r_scout.json()
        assert scout_json["status"] == "success"
        deployed_ep = scout_json["discovery"]["deployed_endpoint"]
        dyn_path = deployed_ep["endpoint_path"]

        r_dyn_unpaid = client.get(dyn_path)
        assert r_dyn_unpaid.status_code == 402
        assert r_dyn_unpaid.json()["payment_details"]["amount"] == "0.05"

        r_dyn_paid = client.get(
            dyn_path, headers={"X-PAYMENT-PROOF": "test_tx_e2e_dynamic_001"}
        )
        assert r_dyn_paid.status_code == 200
        assert "asset" in r_dyn_paid.json()

        # 8. Verify Free Teaser, Base DEX Radar, MCP endpoint & 24h VIP Pass
        r_teaser = client.get("/api/v1/free-teaser")
        assert r_teaser.status_code == 200
        assert r_teaser.json()["status"] == "LIVE_FEED_VERIFIED"

        r_mcp = client.get("/mcp")
        assert r_mcp.status_code == 200
        assert len(r_mcp.json()["tools"]) >= 4

        r_dex_402 = client.get("/api/v1/base-dex-radar")
        assert r_dex_402.status_code == 402
        assert "free_live_teaser" in r_dex_402.json()
        assert "vip_24h_pass_option" in r_dex_402.json()["payment_details"]

        vip_headers = {"X-PAYMENT-PROOF": "test_vip_pass_multi_use_001"}
        r_vip_1 = client.get("/api/v1/base-dex-radar", headers=vip_headers)
        assert r_vip_1.status_code == 200
        assert "top_base_pools" in r_vip_1.json()

        r_vip_2 = client.get("/api/v1/deep-market-report", headers=vip_headers)
        assert r_vip_2.status_code == 200

        r_vip_3 = client.get("/api/v1/crypto-pulse", headers=vip_headers)
        assert r_vip_3.status_code == 200


def test_pin_brute_force_lockout_persisted_in_sqlite(tmp_path: Path):
    """PIN lockout triggers HTTP 429 after 5 failed attempts and persists across memory resets."""
    db_file = str(tmp_path / "test_lockout.db")
    app = create_app(db_path=db_file)

    with TestClient(app) as client:
        for _ in range(settings.MAX_PIN_FAILURES):
            r_fail = client.post("/api/admin/toggle-pause", json={"pin": "wrong"})
            assert r_fail.status_code == 401

        # Simulate server restart by clearing in-memory _pin_failures map
        _pin_failures.clear()

        # SQLite pin_failures table still enforces lockout -> HTTP 429 even with valid PIN
        r_locked = client.post(
            "/api/admin/toggle-pause", json={"pin": settings.ADMIN_PIN}
        )
        assert r_locked.status_code == 429


def test_cron_discover_authentication(tmp_path: Path):
    """/cron/discover requires valid X-Scout-Token or X-Admin-Pin when TESTING=False."""
    db_file = str(tmp_path / "test_scout_auth.db")
    app = create_app(db_path=db_file)

    with TestClient(app) as client:
        settings.TESTING = False
        try:
            # Missing header in production -> 401
            r_no_auth = client.post("/cron/discover")
            assert r_no_auth.status_code == 401

            # Wrong token -> 401
            r_bad_auth = client.post(
                "/cron/discover", headers={"X-Scout-Token": "invalid_secret"}
            )
            assert r_bad_auth.status_code == 401

            # Valid SCOUT_SECRET_TOKEN -> 200
            r_good_auth = client.post(
                "/cron/discover", headers={"X-Scout-Token": settings.SCOUT_SECRET_TOKEN}
            )
            assert r_good_auth.status_code == 200
        finally:
            settings.TESTING = True


def test_production_mode_rejects_test_tokens(tmp_path: Path):
    """When TESTING=False, simulated test_tx_ proofs are rejected with 402 even if mode=='hybrid'."""
    db_file = str(tmp_path / "test_prod_reject.db")
    app = create_app(db_path=db_file)

    with TestClient(app) as client:
        settings.TESTING = False
        settings.X402_VERIFY_MODE = "hybrid"
        try:
            r_prod_reject = client.get(
                "/api/v1/crypto-pulse",
                headers={"X-PAYMENT-PROOF": "test_tx_should_be_rejected_in_prod"},
            )
            assert r_prod_reject.status_code == 402
        finally:
            settings.TESTING = True


def test_concurrent_replay_protection(tmp_path: Path):
    """Two simultaneous requests with the same tx_hash allow only 1 success and reject the other."""
    db_file = str(tmp_path / "test_concurrent.db")
    init_db(db_file)
    shared_tx = "0x" + "b" * 64

    def attempt_record(_: int) -> bool:
        try:
            record_paid_call(
                tx_hash=shared_tx,
                endpoint="/api/v1/crypto-pulse",
                amount_usdc=0.01,
                tier="micro",
                payer_address="0x1111",
                verified_mode="onchain",
                db_path=db_file,
            )
            return True
        except ValueError:
            return False

    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(attempt_record, range(4)))

    # Exactly 1 call succeeds; the other 3 concurrent calls raise ValueError
    assert results.count(True) == 1
    assert results.count(False) == 3


def test_backup_snapshot_export_and_import_roundtrip(tmp_path: Path):
    """Exporting a DB snapshot redacts payer_address and cleanly imports into a fresh DB."""
    db_source = str(tmp_path / "test_snap_src.db")
    db_dest = str(tmp_path / "test_snap_dst.db")
    app = create_app(db_path=db_source)

    with TestClient(app) as client:
        # Unauthenticated snapshot request -> 401
        assert client.get("/api/admin/backup-snapshot").status_code == 401

        # Perform a paid call
        r_paid = client.get(
            "/api/v1/deep-market-report",
            headers={"X-PAYMENT-PROOF": "test_tx_snap_roundtrip_001"},
        )
        assert r_paid.status_code == 200

        # Export via authenticated endpoint
        r_snap = client.get(
            "/api/admin/backup-snapshot",
            headers={"X-Scout-Token": settings.SCOUT_SECRET_TOKEN},
        )
        assert r_snap.status_code == 200
        snapshot = r_snap.json()

    assert snapshot["system_state"]["calls_premium"] == 1
    assert snapshot["used_transactions"][0]["payer_address"] == "redacted"

    # Import into a brand new SQLite DB and verify replay protection is preserved
    restored = import_db_snapshot(snapshot, db_path=db_dest)
    assert restored["calls_premium"] == 1
    assert restored["revenue_usdc"] == 1.0

    with pytest.raises(ValueError):
        record_paid_call(
            tx_hash="test_tx_snap_roundtrip_001",
            endpoint="/api/v1/deep-market-report",
            amount_usdc=1.0,
            tier="premium",
            db_path=db_dest,
        )


@pytest.mark.anyio
async def test_onchain_block_confirmations_check(monkeypatch):
    """When MIN_CONFIRMATIONS > 1, transactions with fewer confirmations are rejected."""
    tx_hash = "0x" + "c" * 64
    recipient_padded = "0x" + settings.WALLET_ADDRESS.lower().replace("0x", "").rjust(
        64, "0"
    )
    payer_padded = "0x" + ("2" * 40).rjust(64, "0")

    class MockResponse:
        def __init__(self, payload):
            self._payload = payload

        def raise_for_status(self):
            pass

        def json(self):
            return self._payload

    async def mock_post(self, url, json, timeout=5.0):
        if json.get("method") == "eth_getTransactionReceipt":
            return MockResponse(
                {
                    "jsonrpc": "2.0",
                    "id": 1,
                    "result": {
                        "status": "0x1",
                        "blockNumber": hex(100),
                        "logs": [
                            {
                                "address": settings.USDC_CONTRACT_ADDRESS,
                                "topics": [
                                    ERC20_TRANSFER_TOPIC,
                                    payer_padded,
                                    recipient_padded,
                                ],
                                "data": hex(10000),
                            }
                        ],
                    },
                }
            )
        # eth_blockNumber returns block 100 -> only 1 confirmation (100 - 100 + 1 = 1)
        return MockResponse({"jsonrpc": "2.0", "id": 2, "result": hex(100)})

    monkeypatch.setattr("httpx.AsyncClient.post", mock_post)

    settings.MIN_CONFIRMATIONS = 3
    try:
        is_valid, _, reason = await verify_base_usdc_transaction(
            tx_hash=tx_hash, expected_amount_usdc=0.01
        )
        assert is_valid is False
        assert "Insufficient block confirmations" in reason
    finally:
        settings.MIN_CONFIRMATIONS = 1


@pytest.mark.anyio
async def test_onchain_block_confirmations_fail_closed_on_rpc_error(monkeypatch):
    """When MIN_CONFIRMATIONS > 1 and eth_blockNumber fails, verification fails closed (rejects)."""
    tx_hash = "0x" + "d" * 64
    recipient_padded = "0x" + settings.WALLET_ADDRESS.lower().replace("0x", "").rjust(
        64, "0"
    )
    payer_padded = "0x" + ("3" * 40).rjust(64, "0")

    class MockResponse:
        def __init__(self, payload):
            self._payload = payload

        def raise_for_status(self):
            pass

        def json(self):
            return self._payload

    async def mock_post(self, url, json, timeout=5.0):
        if json.get("method") == "eth_getTransactionReceipt":
            return MockResponse(
                {
                    "jsonrpc": "2.0",
                    "id": 1,
                    "result": {
                        "status": "0x1",
                        "blockNumber": hex(100),
                        "logs": [
                            {
                                "address": settings.USDC_CONTRACT_ADDRESS,
                                "topics": [
                                    ERC20_TRANSFER_TOPIC,
                                    payer_padded,
                                    recipient_padded,
                                ],
                                "data": hex(10000),
                            }
                        ],
                    },
                }
            )
        raise RuntimeError("Simulated eth_blockNumber RPC outage")

    monkeypatch.setattr("httpx.AsyncClient.post", mock_post)

    settings.MIN_CONFIRMATIONS = 2
    try:
        is_valid, _, reason = await verify_base_usdc_transaction(
            tx_hash=tx_hash, expected_amount_usdc=0.01
        )
        assert is_valid is False
        assert "Unable to verify block confirmations" in reason
    finally:
        settings.MIN_CONFIRMATIONS = 1
