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
