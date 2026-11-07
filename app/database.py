"""
SQLite Database Layer for AIM Network.
Handles persistent storage of:
- System state (ONLINE / PAUSED, call counters, USDC revenue)
- Used transaction hashes (Replay attack protection for x402 payments)
- Autonomous Scout discovery logs (New M2M API opportunities)
"""

import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.config import settings


def get_connection(db_path: Optional[str] = None) -> sqlite3.Connection:
    """Create a thread-safe SQLite connection with WAL mode enabled."""
    target_path = Path(db_path or settings.DATABASE_PATH)
    target_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(target_path), timeout=10.0, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    return conn


def init_db(db_path: Optional[str] = None) -> None:
    """Initialize required tables and seed initial system state."""
    with get_connection(db_path) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS system_state (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                status TEXT NOT NULL DEFAULT 'ONLINE',
                paused INTEGER NOT NULL DEFAULT 0,
                calls_micro INTEGER NOT NULL DEFAULT 0,
                calls_premium INTEGER NOT NULL DEFAULT 0,
                revenue_usdc REAL NOT NULL DEFAULT 0.0,
                updated_at TEXT NOT NULL
            );
            """
        )

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS used_transactions (
                tx_hash TEXT PRIMARY KEY,
                endpoint TEXT NOT NULL,
                amount_usdc REAL NOT NULL,
                payer_address TEXT,
                verified_mode TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            """
        )

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS discovery_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                topic TEXT NOT NULL,
                suggested_endpoint TEXT NOT NULL,
                suggested_price_usdc REAL NOT NULL,
                rationale TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'IDENTIFIED',
                created_at TEXT NOT NULL
            );
            """
        )

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS dynamic_endpoints (
                slug TEXT PRIMARY KEY,
                endpoint_path TEXT NOT NULL UNIQUE,
                asset_name TEXT NOT NULL,
                asset_symbol TEXT NOT NULL,
                coingecko_id TEXT NOT NULL,
                price_usdc REAL NOT NULL DEFAULT 0.05,
                calls_count INTEGER NOT NULL DEFAULT 0,
                revenue_usdc REAL NOT NULL DEFAULT 0.0,
                created_at TEXT NOT NULL
            );
            """
        )

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS vip_passes (
                tx_hash TEXT PRIMARY KEY,
                payer_address TEXT,
                amount_usdc REAL NOT NULL,
                calls_used INTEGER NOT NULL DEFAULT 0,
                max_calls INTEGER NOT NULL DEFAULT 1000,
                expires_at TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            """
        )

        now = datetime.now(timezone.utc).isoformat()
        conn.execute(
            """
            INSERT OR IGNORE INTO system_state (id, status, paused, calls_micro, calls_premium, revenue_usdc, updated_at)
            VALUES (1, 'ONLINE', 0, 0, 0, 0.0, ?);
            """,
            (now,),
        )

        # Seed an initial discovery log if empty so Dashboard immediately looks rich
        cur = conn.execute("SELECT COUNT(*) as cnt FROM discovery_logs;")
        if cur.fetchone()["cnt"] == 0:
            conn.execute(
                """
                INSERT INTO discovery_logs (topic, suggested_endpoint, suggested_price_usdc, rationale, status, created_at)
                VALUES (?, ?, ?, ?, ?, ?);
                """,
                (
                    "Base L2 DEX Liquidity & Whale Inflows",
                    "/api/v1/base-whale-radar",
                    0.05,
                    "Hög efterfrågan från autonoma trading-botar på Base efter realtidsflöden i USDC-pooler.",
                    "QUEUED_FOR_AUTOPILOT",
                    now,
                ),
            )
        conn.commit()


def get_stats(db_path: Optional[str] = None) -> Dict[str, Any]:
    """Return current system status, counters, recent transactions, and scout logs."""
    init_db(db_path)
    with get_connection(db_path) as conn:
        state_row = conn.execute("SELECT * FROM system_state WHERE id = 1;").fetchone()
        discoveries = conn.execute(
            "SELECT * FROM discovery_logs ORDER BY id DESC LIMIT 8;"
        ).fetchall()
        dynamic_eps = conn.execute(
            "SELECT * FROM dynamic_endpoints ORDER BY created_at DESC LIMIT 12;"
        ).fetchall()
        vip_rows = conn.execute(
            "SELECT * FROM vip_passes ORDER BY created_at DESC LIMIT 10;"
        ).fetchall()
        recent_txs = conn.execute(
            "SELECT * FROM used_transactions ORDER BY created_at DESC LIMIT 10;"
        ).fetchall()

        return {
            "status": state_row["status"],
            "paused": bool(state_row["paused"]),
            "calls_micro": state_row["calls_micro"],
            "calls_premium": state_row["calls_premium"],
            "revenue_usdc": round(float(state_row["revenue_usdc"]), 4),
            "updated_at": state_row["updated_at"],
            "discoveries": [dict(row) for row in discoveries],
            "dynamic_endpoints": [dict(row) for row in dynamic_eps],
            "vip_passes": [dict(row) for row in vip_rows],
            "recent_transactions": [dict(row) for row in recent_txs],
        }


def is_tx_used(tx_hash: str, db_path: Optional[str] = None) -> bool:
    """Check if a payment proof transaction hash has already been redeemed."""
    init_db(db_path)
    normalized = tx_hash.strip().lower()
    with get_connection(db_path) as conn:
        row = conn.execute(
            "SELECT 1 FROM used_transactions WHERE tx_hash = ?;", (normalized,)
        ).fetchone()
        return row is not None


def record_paid_call(
    tx_hash: str,
    endpoint: str,
    amount_usdc: float,
    tier: str = "micro",
    payer_address: str = "unknown",
    verified_mode: str = "hybrid",
    db_path: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Atomically record a redeemed transaction hash and increment revenue & call stats.
    Raises ValueError if tx_hash was already used.
    """
    init_db(db_path)
    normalized = tx_hash.strip().lower()
    now = datetime.now(timezone.utc).isoformat()

    with get_connection(db_path) as conn:
        try:
            conn.execute(
                """
                INSERT INTO used_transactions (tx_hash, endpoint, amount_usdc, payer_address, verified_mode, created_at)
                VALUES (?, ?, ?, ?, ?, ?);
                """,
                (normalized, endpoint, amount_usdc, payer_address, verified_mode, now),
            )
        except sqlite3.IntegrityError as exc:
            raise ValueError(f"Transaction hash already used: {normalized}") from exc

        if tier == "premium":
            conn.execute(
                """
                UPDATE system_state
                SET calls_premium = calls_premium + 1,
                    revenue_usdc = ROUND(revenue_usdc + ?, 4),
                    updated_at = ?
                WHERE id = 1;
                """,
                (amount_usdc, now),
            )
        else:
            conn.execute(
                """
                UPDATE system_state
                SET calls_micro = calls_micro + 1,
                    revenue_usdc = ROUND(revenue_usdc + ?, 4),
                    updated_at = ?
                WHERE id = 1;
                """,
                (amount_usdc, now),
            )
        conn.commit()

    return get_stats(db_path)


def set_pause_state(paused: bool, db_path: Optional[str] = None) -> Dict[str, Any]:
    """Set or toggle the Emergency Stop (pause) state."""
    init_db(db_path)
    now = datetime.now(timezone.utc).isoformat()
    status_str = "PAUSED" if paused else "ONLINE"
    with get_connection(db_path) as conn:
        conn.execute(
            """
            UPDATE system_state
            SET paused = ?, status = ?, updated_at = ?
            WHERE id = 1;
            """,
            (1 if paused else 0, status_str, now),
        )
        conn.commit()
    return get_stats(db_path)


def add_discovery_log(
    topic: str,
    suggested_endpoint: str,
    suggested_price_usdc: float,
    rationale: str,
    status: str = "QUEUED_FOR_AUTOPILOT",
    db_path: Optional[str] = None,
) -> Dict[str, Any]:
    """Insert a new autonomous scout API suggestion."""
    init_db(db_path)
    now = datetime.now(timezone.utc).isoformat()
    with get_connection(db_path) as conn:
        cur = conn.execute(
            """
            INSERT INTO discovery_logs (topic, suggested_endpoint, suggested_price_usdc, rationale, status, created_at)
            VALUES (?, ?, ?, ?, ?, ?);
            """,
            (topic, suggested_endpoint, suggested_price_usdc, rationale, status, now),
        )
        conn.commit()
        row_id = cur.lastrowid
        row = conn.execute(
            "SELECT * FROM discovery_logs WHERE id = ?;", (row_id,)
        ).fetchone()
        return dict(row)


def register_dynamic_endpoint(
    slug: str,
    asset_name: str,
    asset_symbol: str,
    coingecko_id: str,
    price_usdc: float = 0.05,
    db_path: Optional[str] = None,
) -> Dict[str, Any]:
    """Register or return an auto-built dynamic M2M endpoint."""
    init_db(db_path)
    clean_slug = slug.lower().strip()
    endpoint_path = f"/api/v1/trending/{clean_slug}"
    now = datetime.now(timezone.utc).isoformat()
    with get_connection(db_path) as conn:
        conn.execute(
            """
            INSERT OR IGNORE INTO dynamic_endpoints
            (slug, endpoint_path, asset_name, asset_symbol, coingecko_id, price_usdc, calls_count, revenue_usdc, created_at)
            VALUES (?, ?, ?, ?, ?, ?, 0, 0.0, ?);
            """,
            (clean_slug, endpoint_path, asset_name, asset_symbol, coingecko_id, price_usdc, now),
        )
        conn.commit()
        row = conn.execute(
            "SELECT * FROM dynamic_endpoints WHERE slug = ?;", (clean_slug,)
        ).fetchone()
        return dict(row)


def increment_dynamic_endpoint_stats(
    slug: str, amount_usdc: float, db_path: Optional[str] = None
) -> None:
    """Increment call counter and revenue on a specific dynamic endpoint."""
    init_db(db_path)
    with get_connection(db_path) as conn:
        conn.execute(
            """
            UPDATE dynamic_endpoints
            SET calls_count = calls_count + 1,
                revenue_usdc = ROUND(revenue_usdc + ?, 4)
            WHERE slug = ?;
            """,
            (amount_usdc, slug.lower().strip()),
        )
        conn.commit()


def check_and_use_vip_pass(
    tx_hash: str, tier: str = "micro", db_path: Optional[str] = None
) -> Optional[Dict[str, Any]]:
    """
    If tx_hash is an active, non-expired 24h VIP pass with remaining calls,
    increment its call usage and system call count without charging again.
    """
    init_db(db_path)
    normalized = tx_hash.strip().lower()
    now_dt = datetime.now(timezone.utc)
    now_iso = now_dt.isoformat()

    with get_connection(db_path) as conn:
        row = conn.execute(
            "SELECT * FROM vip_passes WHERE tx_hash = ?;", (normalized,)
        ).fetchone()
        if not row:
            return None

        expires_dt = datetime.fromisoformat(row["expires_at"])
        if now_dt >= expires_dt or row["calls_used"] >= row["max_calls"]:
            return None

        conn.execute(
            """
            UPDATE vip_passes
            SET calls_used = calls_used + 1
            WHERE tx_hash = ?;
            """,
            (normalized,),
        )
        col = "calls_premium" if tier == "premium" else "calls_micro"
        conn.execute(
            f"UPDATE system_state SET {col} = {col} + 1, updated_at = ? WHERE id = 1;",
            (now_iso,),
        )
        conn.commit()
        updated = conn.execute(
            "SELECT * FROM vip_passes WHERE tx_hash = ?;", (normalized,)
        ).fetchone()
        return dict(updated)


def create_vip_pass(
    tx_hash: str,
    amount_usdc: float,
    payer_address: str = "unknown",
    tier: str = "premium",
    verified_mode: str = "hybrid",
    db_path: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Create a 24h VIP Pass (up to 1,000 calls across all endpoints) and record initial revenue.
    """
    init_db(db_path)
    normalized = tx_hash.strip().lower()
    now_dt = datetime.now(timezone.utc)
    now_iso = now_dt.isoformat()
    expires_iso = (
        now_dt + timedelta(hours=settings.VIP_PASS_DURATION_HOURS)
    ).isoformat()

    record_paid_call(
        tx_hash=normalized,
        endpoint="/api/v1/vip-24h-pass",
        amount_usdc=amount_usdc,
        tier=tier,
        payer_address=payer_address,
        verified_mode=verified_mode,
        db_path=db_path,
    )

    with get_connection(db_path) as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO vip_passes
            (tx_hash, payer_address, amount_usdc, calls_used, max_calls, expires_at, created_at)
            VALUES (?, ?, ?, 1, ?, ?, ?);
            """,
            (
                normalized,
                payer_address,
                amount_usdc,
                settings.VIP_PASS_MAX_CALLS,
                expires_iso,
                now_iso,
            ),
        )
        conn.commit()
        row = conn.execute(
            "SELECT * FROM vip_passes WHERE tx_hash = ?;", (normalized,)
        ).fetchone()
        return dict(row)



