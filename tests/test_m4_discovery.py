"""
Unit tests for Milestone M4: Self-Marketing Discovery Manifests & Autonomous Scout.
"""

from pathlib import Path
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.config import settings
from app.database import init_db, get_stats
from app.routers.discovery import router as discovery_router


def create_m4_app(db_path: str) -> FastAPI:
    app = FastAPI()
    app.state.db_path = db_path
    app.include_router(discovery_router)
    return app


def test_discovery_manifests_and_scout(tmp_path: Path):
    """Verify /llms.txt, /agents.json, /.well-known/agent.json and /cron/discover."""
    db_file = str(tmp_path / "test_m4.db")
    init_db(db_file)
    client = TestClient(create_m4_app(db_file))

    # 1. /llms.txt
    r_llms = client.get("/llms.txt")
    assert r_llms.status_code == 200
    assert settings.WALLET_ADDRESS in r_llms.text
    assert "/api/v1/crypto-pulse" in r_llms.text
    assert "/api/v1/deep-market-report" in r_llms.text

    # 2. /agents.json & /.well-known/agent.json
    r_agents = client.get("/agents.json")
    assert r_agents.status_code == 200
    agents_data = r_agents.json()
    assert agents_data["auth"]["recipient_wallet"] == settings.WALLET_ADDRESS
    assert len(agents_data["endpoints"]) >= 4

    r_wk = client.get("/.well-known/agent.json")
    assert r_wk.status_code == 200
    assert r_wk.json()["auth"]["type"] == "x402"

    # 3. /cron/discover
    r_scout = client.post("/cron/discover")
    assert r_scout.status_code == 200
    scout_data = r_scout.json()
    assert scout_data["status"] == "success"
    assert "suggested_endpoint" in scout_data["discovery"]

    stats = get_stats(db_file)
    assert len(stats["discoveries"]) >= 2

