"""Admin endpoint protection, per-client lockout and keep-alive classification."""

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
