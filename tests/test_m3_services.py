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


def test_canonical_trending_endpoints_sample_and_paid(tmp_path: Path):
    """X1: Verify canonical trending assets (morpho, virtual) respond to /trending/{slug} for both sample and paid calls."""
    from app.main import create_app

    db_file = str(tmp_path / "test_m3_trending_slugs.db")
    app = create_app(db_path=db_file)
    client = TestClient(app)

    # 1. Sample verification mode (?sample=true)
    r_morpho_sample = client.get("/api/v1/trending/morpho?sample=true")
    assert r_morpho_sample.status_code == 200
    assert r_morpho_sample.json()["sample_mode"] is True
    assert r_morpho_sample.json()["payload"]["asset"]["symbol"] == "MORPHO"

    r_virtual_sample = client.get("/api/v1/trending/virtual?sample=true")
    assert r_virtual_sample.status_code == 200
    assert r_virtual_sample.json()["sample_mode"] is True
    assert r_virtual_sample.json()["payload"]["asset"]["symbol"] == "VIRTUAL"

    # 2. Unpaid -> 402 Payment Required
    r_unpaid = client.get("/api/v1/trending/morpho")
    assert r_unpaid.status_code == 402
    assert r_unpaid.json()["payment_details"]["amount"] == "0.05"

    # 3. Paid with test token -> 200 OK
    r_paid = client.get(
        "/api/v1/trending/morpho",
        headers={"X-PAYMENT-PROOF": "test_tx_morpho_paid_001"},
    )
    assert r_paid.status_code == 200
    assert r_paid.json()["status"] == "ok"
    assert r_paid.json()["asset"]["slug"] == "morpho"
    assert r_paid.json()["asset"]["dex"] == "Aerodrome / Base"


def test_synthetic_scout_seed_timestamp_isolation(tmp_path: Path):
    """X2: Verify synthetic scout seeds in /api/v1/trending have data_as_of: null and data_age_seconds: null."""
    from app.main import create_app
    from app.database import register_dynamic_endpoint

    db_file = str(tmp_path / "test_m3_synthetic.db")
    app = create_app(db_path=db_file)
    client = TestClient(app)

    # Deploy a synthetic scout endpoint
    register_dynamic_endpoint(
        slug="wasted",
        asset_name="WASTED",
        asset_symbol="WASTED",
        coingecko_id="wasted",
        price_usdc=0.05,
        db_path=db_file,
    )

    r = client.get("/api/v1/trending")
    assert r.status_code == 200
    assets = r.json().get("trending_assets", [])
    wasted = next((a for a in assets if a["slug"] == "wasted"), None)
    assert wasted is not None
    assert wasted["is_synthetic"] is True
    assert wasted["data_as_of"] is None
    assert wasted["data_age_seconds"] is None




class _FakeResponse:
    def __init__(self, status_code, payload):
        self.status_code = status_code
        self._payload = payload

    def json(self):
        return self._payload


class _FakeAsyncClient:
    """Stands in for httpx.AsyncClient in market_data fallback tests."""

    ok = True

    def __init__(self, *args, **kwargs):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc_info):
        return False

    async def get(self, url):
        if not _FakeAsyncClient.ok:
            return _FakeResponse(429, {})
        addresses = (
            "0xbaa5cc21fd487b8fcc2f632f3f4e8d37262a0842",
            "0x0b3e328455c4059ee9e3f84b5543f74e24e7e1b",
        )
        pairs = [
            {
                "chainId": "base",
                "dexId": "aerodrome",
                "baseToken": {"address": address},
                "liquidity": {"usd": 900000.0},
                "volume": {"h24": 250000.0},
                "priceChange": {"h24": -1.5},
                "pairCreatedAt": None,
            }
            for address in addresses
        ]
        return _FakeResponse(200, {"pairs": pairs})


def test_paid_canonical_withholds_seed_data_without_charging(tmp_path, monkeypatch):
    """Y2: a degraded feed must yield 503 instead of selling hardcoded seed values."""
    import app.routers.api_v1 as api_v1
    from app.database import get_stats
    from app.main import create_app
    from fastapi.testclient import TestClient

    async def seed_feed():
        return {
            "tokens": [
                {
                    "slug": "morpho",
                    "asset_name": "Morpho",
                    "asset_symbol": "MORPHO",
                    "liquidity_usd": 984877.14,
                    "volume_24h_usd": 299740.5,
                    "momentum_24h_pct": -1.99,
                    "pool_age_days": 245,
                    "liquidity_class": "DEEP_LIQUIDITY",
                    "dex": "Aerodrome / Base",
                    "is_stale": True,
                }
            ],
            "data_as_of": None,
            "data_age_seconds": None,
            "source": "static_seed",
            "is_stale": True,
            "fallback_reason": "DexScreener HTTP 429",
        }

    monkeypatch.setattr(api_v1, "fetch_trending_dex_tokens", seed_feed)
    db_file = str(tmp_path / "test_y2_seed.db")
    client = TestClient(create_app(db_path=db_file))

    paid = client.get(
        "/api/v1/trending/morpho", headers={"X-PAYMENT-PROOF": "test_tx_y2_seed_001"}
    )
    assert paid.status_code == 503
    body = paid.json()
    assert body["status"] == "DATA_QUALITY_UNAVAILABLE"
    assert body["meta"]["fallback_reason"] == "DexScreener HTTP 429"
    assert paid.headers["retry-after"] == "60"
    assert get_stats(db_file)["total_calls"] == 0

    sample = client.get("/api/v1/trending/morpho?sample=true")
    assert sample.status_code == 200


def test_paid_canonical_flags_live_data_and_records_telemetry(tmp_path, monkeypatch):
    """Y2/Y3: paid live payload carries staleness flags and per-endpoint counters accumulate."""
    import app.routers.api_v1 as api_v1
    from app.database import get_stats
    from app.main import create_app
    from fastapi.testclient import TestClient

    async def live_feed():
        return {
            "tokens": [
                {
                    "slug": "morpho",
                    "asset_name": "Morpho",
                    "asset_symbol": "MORPHO",
                    "liquidity_usd": 1529378.06,
                    "volume_24h_usd": 295494.56,
                    "momentum_24h_pct": -1.75,
                    "pool_age_days": None,
                    "liquidity_class": "DEEP_LIQUIDITY",
                    "dex": "Aerodrome / Base",
                    "is_stale": False,
                }
            ],
            "data_as_of": "2026-11-08T15:39:11+00:00",
            "data_age_seconds": 0,
            "source": "dexscreener_base_live",
            "is_stale": False,
            "fallback_reason": None,
        }

    monkeypatch.setattr(api_v1, "fetch_trending_dex_tokens", live_feed)
    db_file = str(tmp_path / "test_y3_live.db")
    client = TestClient(create_app(db_path=db_file))

    r = client.get(
        "/api/v1/trending/morpho", headers={"X-PAYMENT-PROOF": "test_tx_y3_live_001"}
    )
    assert r.status_code == 200
    body = r.json()
    assert body["asset"]["is_stale"] is False
    assert body["asset"]["is_synthetic"] is False
    assert body["meta"]["is_stale"] is False
    assert body["meta"]["fallback_reason"] is None

    stats = get_stats(db_file)
    row = next(ep for ep in stats["dynamic_endpoints"] if ep["slug"] == "morpho")
    assert row["calls_count"] == 1
    assert abs(row["revenue_usdc"] - 0.05) < 1e-9


def test_trending_serves_last_good_live_instead_of_seed(monkeypatch):
    """Y1: throttling falls back to the last real observation with an age, not to seed values."""
    import asyncio
    import app.services.market_data as md

    md._cache_store.pop("trending_dex_tokens", None)
    md._last_good_live.clear()
    monkeypatch.setattr(md.httpx, "AsyncClient", _FakeAsyncClient)

    _FakeAsyncClient.ok = True
    live = asyncio.run(md.fetch_trending_dex_tokens())
    assert live["source"] == "dexscreener_base_live"
    assert live["is_stale"] is False

    md._cache_store.pop("trending_dex_tokens", None)
    _FakeAsyncClient.ok = False
    stale = asyncio.run(md.fetch_trending_dex_tokens())
    assert stale["source"] == md.TRENDING_LAST_GOOD_SOURCE
    assert stale["is_stale"] is True
    assert stale["data_as_of"] == live["data_as_of"]
    assert isinstance(stale["data_age_seconds"], int)
    assert all(token["is_stale"] for token in stale["tokens"])
    assert stale["fallback_reason"] == "DexScreener HTTP 429"

    md._cache_store.pop("trending_dex_tokens", None)
    md._last_good_live.clear()
    _FakeAsyncClient.ok = True


def test_pro_tier_threshold_follows_config(tmp_path, monkeypatch):
    """Y4: the Pro threshold must come from config, not a hardcoded 10.0."""
    from decimal import Decimal
    from app.config import settings
    from app.database import create_vip_pass

    monkeypatch.setattr(settings, "PRO_PASS_PRICE_DEC", Decimal("12.00"))
    db_file = str(tmp_path / "test_y4_pro.db")

    below = create_vip_pass(
        tx_hash="test_vip_cfg_below_001", amount_usdc=11.5, db_path=db_file
    )
    assert below["tier"] == "micro"

    above = create_vip_pass(
        tx_hash="test_vip_cfg_above_001", amount_usdc=12.5, db_path=db_file
    )
    assert above["tier"] == "pro"
