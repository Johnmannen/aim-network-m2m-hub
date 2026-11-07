"""
SQLite Database Layer for AIM Network.
Handles persistent storage of:
- System state (ONLINE / PAUSED, call counters, USDC revenue)
- Used transaction hashes (Replay attack protection for x402 payments)
- Autonomous Scout discovery logs (New M2M API opportunities)
"""

import sqlite3
from datetime import datetime, timezone
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
            "SELECT * FROM discovery_logs ORDER BY id DESC LIMIT 5;"
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

