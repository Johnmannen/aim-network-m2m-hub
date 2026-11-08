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
    r = c.get("/admin")
    assert r.status_code == 200
    assert "Logga in" in r.text
    assert "USDC" not in r.text and "Intäkt" not in r.text


def test_dashboard_login_flow(tmp_path):
    c = _client(tmp_path)
    assert c.post("/api/admin/login", json={"pin": "wrong"}).status_code == 401
    assert c.get("/admin").text.count("Logga in") >= 1
    ok = c.post("/api/admin/login", json={"pin": settings.ADMIN_PIN})
    assert ok.status_code == 200
    page = c.get("/admin")
    assert "Logga in" not in page.text
    # session cookie also unlocks admin JSON endpoints
    assert c.get("/api/admin/stats").status_code == 200


def test_forged_session_cookie_rejected(tmp_path):
    c = _client(tmp_path)
    c.cookies.set("aim_admin", "9999999999.deadbeef")
    assert "Logga in" in c.get("/admin").text
    assert c.get("/api/admin/stats").status_code == 401


def test_session_unlocks_preview_product(tmp_path):
    c = _client(tmp_path)
    assert c.get("/api/admin/preview-product").status_code == 401
    c.post("/api/admin/login", json={"pin": settings.ADMIN_PIN})
    assert c.get("/api/admin/preview-product?endpoint=/api/v1/crypto-pulse").status_code == 200
    # Verify dashboard HTML contains logout button and /api/admin/logout clears session
    assert "logoutAdmin()" in c.get("/admin").text
    assert c.post("/api/admin/logout").status_code == 200
    assert c.get("/api/admin/preview-product").status_code == 401


def test_public_landing_and_content_negotiation(tmp_path):
    c = _client(tmp_path)
    # Default HTML response for human browsers
    r_html = c.get("/")
    assert r_html.status_code == 200
    assert "AIM Network" in r_html.text
    assert "Autonomous Machine-to-Machine" in r_html.text
    assert "/admin" in r_html.text

    # Content negotiation: Accept: application/json returns discovery manifest
    r_json = c.get("/", headers={"Accept": "application/json"})
    assert r_json.status_code == 200
    data = r_json.json()
    assert "AIM Network" in data["name"]
    assert "endpoints" in data
    assert "/llms.txt" in data["catalogs"]["llms_txt"]


def test_head_requests_and_scanner_block(tmp_path):
    c = _client(tmp_path)
    # HEAD requests on discovery and health routes
    assert c.head("/").status_code == 200
    assert c.head("/health").status_code == 200
    assert c.head("/llms.txt").status_code == 200
    assert c.head("/agents.json").status_code == 200

    # Scanner blocking: .php and .env paths return fast 404 Not Found without route dispatch
    res_php = c.get("/wp-login.php")
    assert res_php.status_code == 404
    assert res_php.json()["detail"] == "Not Found"

    res_env = c.get("/.env")
    assert res_env.status_code == 404


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


def test_admin_simulate_and_reset_purchase(tmp_path):
    c = _client(tmp_path)
    # Unauthenticated calls must fail with 401
    assert c.post("/api/admin/simulate-purchase").status_code == 401
    assert c.post("/api/admin/reset-simulations").status_code == 401

    # Log in as admin
    c.post("/api/admin/login", json={"pin": settings.ADMIN_PIN})

    # Trigger 1-click simulated purchase
    sim = c.post("/api/admin/simulate-purchase")
    assert sim.status_code == 200
    assert sim.json()["status"] == "simulated_purchase_complete"

    stats_after_sim = c.get("/api/admin/stats").json()
    assert stats_after_sim["calls_micro"] == 1
    assert stats_after_sim["revenue_usdc"] == 0.01
    assert stats_after_sim["traffic_telemetry"]["paid_200"] == 1

    # Trigger 1-click reset of simulated purchases
    rst = c.post("/api/admin/reset-simulations")
    assert rst.status_code == 200
    assert rst.json()["stats"]["calls_micro"] == 0
    assert rst.json()["stats"]["revenue_usdc"] == 0.0
    assert rst.json()["stats"]["traffic_telemetry"]["paid_200"] == 0


def test_admin_cookie_requests_excluded_from_external_traffic_and_clear_traffic(tmp_path):
    c = _client(tmp_path)
    # 1. External bot request (no admin cookie) IS counted in external traffic
    c.get("/llms.txt", headers={"User-Agent": "GPTBot/1.0"})
    # 2. Internal diagnostic probe (aim-internal-probe) is NOT counted
    c.get("/llms.txt", headers={"User-Agent": "aim-internal-probe"})

    # 3. Log in as admin (sets aim_admin cookie)
    c.post("/api/admin/login", json={"pin": settings.ADMIN_PIN})
    # Admin clicking /llms.txt or /agents.json with aim_admin cookie is NOT counted as external traffic
    c.get("/llms.txt")
    c.get("/agents.json")

    stats = c.get("/api/admin/stats").json()
    assert stats["traffic_telemetry"]["total_external_requests"] == 1

    # 4. Clear traffic logs via /api/admin/clear-traffic
    clr = c.post("/api/admin/clear-traffic")
    assert clr.status_code == 200
    assert clr.json()["stats"]["traffic_telemetry"]["total_external_requests"] == 0


def test_mcp_jsonrpc_handshake_and_glama_claim(tmp_path):
    c = _client(tmp_path)
    # 1. Verify Glama claim token at both /mcp/.well-known/glama.json and /.well-known/glama.json
    for glama_path in ("/mcp/.well-known/glama.json", "/.well-known/glama.json"):
        r_claim = c.get(glama_path)
        assert r_claim.status_code == 200
        assert r_claim.json()["claim"] == "glama_claim_kMQwR0tBTjmF1CxnpiYj2Cgs6m2DT753"

    # 2. Verify MCP JSON-RPC 2.0 initialize -> notifications/initialized -> tools/list -> tools/call
    r_init = c.post(
        "/mcp",
        json={
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "glama-healthcheck", "version": "1.0.0"},
            },
        },
    )
    assert r_init.status_code == 200
    assert r_init.json()["result"]["serverInfo"]["name"] == "aim-network-m2m-hub"

    r_notif = c.post(
        "/mcp",
        json={"jsonrpc": "2.0", "method": "notifications/initialized"},
    )
    assert r_notif.status_code == 202

    r_tools = c.post(
        "/mcp",
        json={"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}},
    )
    assert r_tools.status_code == 200
    tools = r_tools.json()["result"]["tools"]
    assert len(tools) >= 4
    for t in tools:
        assert "inputSchema" in t
        assert t["inputSchema"]["type"] == "object"

    r_call = c.post(
        "/mcp",
        json={
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {"name": "get_free_market_teaser", "arguments": {}},
        },
    )
    assert r_call.status_code == 200
    assert r_call.json()["result"]["isError"] is False
