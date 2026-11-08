"""
Unit tests for Milestone M3: Live M2M API Services ($0.01 & $1.00 endpoints).
"""

import time
from pathlib import Path
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.database import init_db, get_stats
from app.routers.api_v1 import router as api_v1_router


def create_m3_app(db_path: str) -> FastAPI:
    app = FastAPI()
    app.state.db_path = db_path
    app.include_router(api_v1_router)
    return app


def test_crypto_pulse_and_deep_report_flow(tmp_path: Path):
    """Verify both paid endpoints enforce 402 without proof and deliver rich JSON with proof."""
    db_file = str(tmp_path / "test_m3.db")
    init_db(db_file)
    client = TestClient(create_m3_app(db_file))

    # 1. Without proof -> 402
    r1 = client.get("/api/v1/crypto-pulse")
    assert r1.status_code == 402
    assert r1.json()["payment_details"]["amount"] == "0.01"

    r2 = client.get("/api/v1/deep-market-report")
    assert r2.status_code == 402
    assert r2.json()["payment_details"]["amount"] == "1.00"

    # 2. With valid proof -> 200 OK & structured payload
    r1_paid = client.get(
        "/api/v1/crypto-pulse", headers={"X-PAYMENT-PROOF": "test_tx_m3_pulse_001"}
    )
    assert r1_paid.status_code == 200
    pulse_json = r1_paid.json()
    assert "assets" in pulse_json
    assert "BTC" in pulse_json["assets"]
    assert "fear_and_greed" in pulse_json
    assert "volatility_index_24h" in pulse_json

    # 3. Verify second call hits TTL cache in < 0.1s
    t0 = time.perf_counter()
    r2_paid = client.get(
        "/api/v1/deep-market-report", headers={"X-PAYMENT-PROOF": "test_tx_m3_deep_001"}
    )
    elapsed = time.perf_counter() - t0
    assert r2_paid.status_code == 200
    assert elapsed < 0.5
    deep_json = r2_paid.json()
    assert "actionable_signals" in deep_json
    assert len(deep_json["actionable_signals"]) >= 2
    assert "base_l2_ecosystem_metrics" in deep_json

    stats = get_stats(db_file)
    assert stats["calls_micro"] == 1
    assert stats["calls_premium"] == 1
    assert stats["revenue_usdc"] == 1.01


def test_sample_mode_bypasses_x402_for_schema_preview(tmp_path: Path):
    """Verify ?sample=true delivers free schema preview with sample_mode metadata without x402 payment."""
    from app.main import create_app

    db_file = str(tmp_path / "test_m3_sample.db")
    app = create_app(db_path=db_file)
    client = TestClient(app)

    # 1. /api/v1/crypto-pulse?sample=true
    r_pulse_sample = client.get("/api/v1/crypto-pulse?sample=true")
    assert r_pulse_sample.status_code == 200
    d_pulse = r_pulse_sample.json()
    assert d_pulse["sample_mode"] is True
    assert "SAMPLE ONLY" in d_pulse["sample_notice"]
    assert "payload" in d_pulse
    assert "BTC" in d_pulse["payload"]["assets"]

    # HEAD on sample
    assert client.head("/api/v1/crypto-pulse?sample=true").status_code == 200

    # 2. /api/v1/base-dex-radar?sample=true
    r_radar_sample = client.get("/api/v1/base-dex-radar?sample=true")
    assert r_radar_sample.status_code == 200
    assert r_radar_sample.json()["sample_mode"] is True

    # 3. /api/v1/deep-market-report?sample=true
    r_deep_sample = client.get("/api/v1/deep-market-report?sample=true")
    assert r_deep_sample.status_code == 200
    assert r_deep_sample.json()["sample_mode"] is True

    # 4. Verify OpenAPI schema exposes x402 metadata
    r_openapi = client.get("/openapi.json")
    assert r_openapi.status_code == 200
    schema = r_openapi.json()
    assert schema["info"]["x-payment-protocol"] == "x402"
    assert schema["info"]["x-payment-chain-id"] == 8453
    pulse_op = schema["paths"]["/api/v1/crypto-pulse"]["get"]
    assert pulse_op["x-payment-protocol"] == "x402"
    assert pulse_op["x-sample-url"] == "/api/v1/crypto-pulse?sample=true"

