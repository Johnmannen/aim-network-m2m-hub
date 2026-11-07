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
        assert len(r_agents.json()["endpoints"]) >= 4

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

        # 7. Run Autonomous Scout & verify auto-deployed live endpoint works
        r_scout = client.post("/cron/discover")
        assert r_scout.status_code == 200
        scout_json = r_scout.json()
        assert scout_json["status"] == "success"
        deployed_ep = scout_json["discovery"]["deployed_endpoint"]
        dyn_path = deployed_ep["endpoint_path"]

        # Unpaid call to auto-deployed endpoint returns 402 ($0.05 USDC)
        r_dyn_unpaid = client.get(dyn_path)
        assert r_dyn_unpaid.status_code == 402
        assert r_dyn_unpaid.json()["payment_details"]["amount"] == "0.05"

        # Paid call to auto-deployed endpoint returns 200 OK
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

        # Base DEX Radar without proof -> 402 with free_live_teaser & vip_24h_pass_option
        r_dex_402 = client.get("/api/v1/base-dex-radar")
        assert r_dex_402.status_code == 402
        assert "free_live_teaser" in r_dex_402.json()
        assert "vip_24h_pass_option" in r_dex_402.json()["payment_details"]

        # 24h VIP Pass (`test_vip_...`) allows multiple calls across all endpoints with same tx_hash!
        vip_headers = {"X-PAYMENT-PROOF": "test_vip_pass_multi_use_001"}
        r_vip_1 = client.get("/api/v1/base-dex-radar", headers=vip_headers)
        assert r_vip_1.status_code == 200
        assert "top_base_pools" in r_vip_1.json()

        r_vip_2 = client.get("/api/v1/deep-market-report", headers=vip_headers)
        assert r_vip_2.status_code == 200

        r_vip_3 = client.get("/api/v1/crypto-pulse", headers=vip_headers)
        assert r_vip_3.status_code == 200

        # 9. Verify Live Traffic & Conversion Radar telemetry
        r_telemetry = client.get("/api/admin/stats")
        assert r_telemetry.status_code == 200
        tel = r_telemetry.json()["traffic_telemetry"]
        assert tel["discovery_hits"] >= 3
        assert tel["quotes_402"] >= 3
        assert tel["paid_200"] >= 5
        assert len(tel["recent_stream"]) >= 5

