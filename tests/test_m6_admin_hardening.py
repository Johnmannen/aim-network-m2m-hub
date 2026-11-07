"""Admin endpoint protection, per-client lockout and keep-alive classification."""

import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.database import get_stats, log_traffic_event
from app.main import create_app


def _client(tmp_path):
    return TestClient(create_app(str(tmp_path / "t.db")))


def test_admin_endpoints_require_pin(tmp_path):
    c = _client(tmp_path)
    for url in (
        "/api/admin/stats",
        "/api/admin/preview-product?endpoint=/api/v1/crypto-pulse",
        "/api/admin/self-check",
    ):
        assert c.get(url).status_code == 401
        ok = c.get(url, headers={"X-Admin-Pin": settings.ADMIN_PIN})
        assert ok.status_code == 200, url


def test_lockout_is_per_client_ip(tmp_path):
    settings.TRUST_PROXY_HEADERS = True
    try:
        c = _client(tmp_path)
        for _ in range(settings.MAX_PIN_FAILURES):
            c.get("/api/admin/stats", headers={"X-Admin-Pin": "bad", "CF-Connecting-IP": "1.1.1.1"})
        locked = c.get("/api/admin/stats", headers={"X-Admin-Pin": "bad", "CF-Connecting-IP": "1.1.1.1"})
        assert locked.status_code == 429
        other = c.get(
            "/api/admin/stats",
            headers={"X-Admin-Pin": settings.ADMIN_PIN, "CF-Connecting-IP": "2.2.2.2"},
        )
        assert other.status_code == 200
    finally:
        settings.TRUST_PROXY_HEADERS = False


def test_keepalive_traffic_is_internal(tmp_path):
    db = str(tmp_path / "k.db")
    log_traffic_event("/llms.txt", "GET", 200, user_agent="aim-keepalive", db_path=db)
    assert get_stats(db)["traffic_telemetry"]["total_external_requests"] == 0


def test_dashboard_locked_without_session(tmp_path):
    c = _client(tmp_path)
    r = c.get("/")
    assert r.status_code == 200
    assert "Logga in" in r.text
    assert "USDC" not in r.text and "Intäkt" not in r.text


def test_dashboard_login_flow(tmp_path):
    c = _client(tmp_path)
    assert c.post("/api/admin/login", json={"pin": "wrong"}).status_code == 401
    assert c.get("/").text.count("Logga in") >= 1
    ok = c.post("/api/admin/login", json={"pin": settings.ADMIN_PIN})
    assert ok.status_code == 200
    page = c.get("/")
    assert "Logga in" not in page.text
    # session cookie also unlocks admin JSON endpoints
    assert c.get("/api/admin/stats").status_code == 200


def test_forged_session_cookie_rejected(tmp_path):
    c = _client(tmp_path)
    c.cookies.set("aim_admin", "9999999999.deadbeef")
    assert "Logga in" in c.get("/").text
    assert c.get("/api/admin/stats").status_code == 401


def test_session_unlocks_preview_product(tmp_path):
    c = _client(tmp_path)
    assert c.get("/api/admin/preview-product").status_code == 401
    c.post("/api/admin/login", json={"pin": settings.ADMIN_PIN})
    assert c.get("/api/admin/preview-product?endpoint=/api/v1/crypto-pulse").status_code == 200
    # Verify dashboard HTML contains logout button and /api/admin/logout clears session
    assert "logoutAdmin()" in c.get("/").text
    assert c.post("/api/admin/logout").status_code == 200
    assert c.get("/api/admin/preview-product").status_code == 401


def test_traffic_log_30_day_retention_policy(tmp_path):
    from app.database import get_connection

    db = str(tmp_path / "retention.db")
    log_traffic_event("/llms.txt", "GET", 200, user_agent="Bot/1.0", db_path=db)
    # Manually backdate the existing row to 45 days ago
    with get_connection(db) as conn:
        conn.execute("UPDATE traffic_logs SET created_at = '2020-01-01T00:00:00+00:00';")
        conn.commit()
    # Logging a new event triggers retention cleanup of rows older than 30 days
    log_traffic_event("/agents.json", "GET", 200, user_agent="Bot/1.0", db_path=db)
    stats = get_stats(db)
    assert stats["traffic_telemetry"]["total_external_requests"] == 1


@pytest.mark.anyio
async def test_cloud_gist_push_and_restore_roundtrip(tmp_path, monkeypatch):
    from app.database import record_paid_call
    from app.services.cloud_backup import push_to_cloud_gist, restore_from_cloud_gist

    db_src = str(tmp_path / "gist_src.db")
    db_dst = str(tmp_path / "gist_dst.db")
    record_paid_call(
        tx_hash="0x" + "e" * 64,
        endpoint="/api/v1/crypto-pulse",
        amount_usdc=0.01,
        tier="micro",
        payer_address="0x9999",
        db_path=db_src,
    )

    stored_gist = {}

    class MockGistResp:
        def __init__(self, status_code, data):
            self.status_code = status_code
            self._data = data

        def json(self):
            return self._data

    async def mock_patch(self, url, headers=None, json=None):
        stored_gist["files"] = json["files"]
        return MockGistResp(200, stored_gist)

    async def mock_get(self, url, headers=None):
        return MockGistResp(200, stored_gist)

    monkeypatch.setattr("httpx.AsyncClient.patch", mock_patch)
    monkeypatch.setattr("httpx.AsyncClient.get", mock_get)
    settings.BACKUP_GIST_ID = "test_gist_id_123"
    settings.GITHUB_BACKUP_TOKEN = "test_token_abc"
    try:
        pushed = await push_to_cloud_gist(db_path=db_src)
        assert pushed is True
        restored = await restore_from_cloud_gist(db_path=db_dst)
        assert restored is True
        assert get_stats(db_dst)["calls_micro"] == 1
    finally:
        settings.BACKUP_GIST_ID = ""
        settings.GITHUB_BACKUP_TOKEN = ""
