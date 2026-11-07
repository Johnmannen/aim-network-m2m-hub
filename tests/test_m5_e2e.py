"""
End-to-End (E2E) & Milestone M5 Test Suite for AIM Network.
Validates the entire lifecycle:
1. Discovery manifests (/llms.txt, /agents.json, /.well-known/agent.json)
2. Overseer Dashboard HTML (/) & live stats (/api/admin/stats)
3. x402 Payment Gate (HTTP 402 without proof, HTTP 200 with proof, HTTP 402 on replay)
4. Revenue accounting across Micro ($0.01) and Premium ($1.00) endpoints
5. PIN-protected Emergency Stop (HTTP 401 on wrong PIN, HTTP 503 when paused, HTTP 200 when resumed)
6. Autonomous Scout (/cron/discover)
"""

from pathlib import Path
from fastapi.testclient import TestClient

from app.config import settings
from app.main import create_app


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
        assert len(r_agents.json()["endpoints"]) == 2

        # 2. Dashboard initial render
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
        r_stats = client.get("/api/admin/stats")
        assert r_stats.status_code == 200
        stats_data = r_stats.json()
        assert stats_data["calls_micro"] == 1
        assert stats_data["calls_premium"] == 1
        assert stats_data["revenue_usdc"] == 1.01

        r_dash_after = client.get("/")
        assert "$1.01 USDC" in r_dash_after.text

        # 6. PIN-protected Emergency Stop
        # Wrong PIN -> 401
        r_bad_pin = client.post("/api/admin/toggle-pause", json={"pin": "wrong-pin"})
        assert r_bad_pin.status_code == 401

        # Correct PIN -> Pauses system
        r_pause = client.post(
            "/api/admin/toggle-pause", json={"pin": settings.ADMIN_PIN}
        )
        assert r_pause.status_code == 200
        assert r_pause.json()["paused"] is True

        # While paused, even valid payment gets HTTP 503
        r_paused_call = client.get(
            "/api/v1/crypto-pulse",
            headers={"X-PAYMENT-PROOF": "test_tx_e2e_while_paused"},
        )
        assert r_paused_call.status_code == 503

        # Resume system with correct PIN
        r_resume = client.post(
            "/api/admin/toggle-pause", json={"pin": settings.ADMIN_PIN}
        )
        assert r_resume.status_code == 200
        assert r_resume.json()["paused"] is False

        # Now call succeeds again
        r_resumed_call = client.get(
            "/api/v1/crypto-pulse",
            headers={"X-PAYMENT-PROOF": "test_tx_e2e_after_resume"},
        )
        assert r_resumed_call.status_code == 200

        # 7. Run Autonomous Scout
        r_scout = client.post("/cron/discover")
        assert r_scout.status_code == 200
        assert r_scout.json()["status"] == "success"

