"""
Turso Cloud SQLite Integration & Dual-Write Persistence Service.
Provides persistent cloud storage across Render container restarts:
- When TURSO_DATABASE_URL and TURSO_AUTH_TOKEN are set, syncs transactions,
  discoveries, traffic logs, and system state to Turso via the HTTP Pipeline API.
- On container startup, hydrates the local SQLite database if fresh.
- When Turso credentials are not configured, seamlessly falls back to pure local SQLite.
"""

import logging
from typing import Any, Dict, List, Optional
import httpx

from app.config import settings

logger = logging.getLogger(__name__)


def is_turso_enabled() -> bool:
    """Return True if Turso credentials are configured in environment."""
    return bool(settings.TURSO_DATABASE_URL and settings.TURSO_AUTH_TOKEN)


def _get_turso_http_url() -> str:
    url = settings.TURSO_DATABASE_URL.strip()
    if url.startswith("libsql://"):
        url = "https://" + url[len("libsql://") :]
    if not url.startswith("http"):
        url = f"https://{url}"
    url = url.rstrip("/")
    if not url.endswith("/v2/pipeline"):
        url = f"{url}/v2/pipeline"
    return url


def _format_turso_arg(val: Any) -> Dict[str, Any]:
    """Convert Python value to Turso Hrana v2 Value object."""
    if val is None:
        return {"type": "null"}
    if isinstance(val, int):
        return {"type": "integer", "value": str(val)}
    if isinstance(val, float):
        return {"type": "float", "value": val}
    if isinstance(val, bytes):
        import base64
        return {"type": "blob", "base64": base64.b64encode(val).decode("ascii")}
    return {"type": "text", "value": str(val)}


async def execute_turso_async(sql: str, args: Optional[List[Any]] = None) -> Optional[Dict[str, Any]]:
    """Execute a single SQL statement against Turso via HTTP Pipeline API."""
    if not is_turso_enabled():
        return None

    pipeline_url = _get_turso_http_url()
    headers = {
        "Authorization": f"Bearer {settings.TURSO_AUTH_TOKEN}",
        "Content-Type": "application/json",
    }
    stmt: Dict[str, Any] = {"sql": sql}
    if args:
        stmt["args"] = [_format_turso_arg(a) for a in args]

    payload = {
        "requests": [
            {"type": "execute", "stmt": stmt},
            {"type": "close"},
        ]
    }

    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            resp = await client.post(pipeline_url, headers=headers, json=payload)
            if resp.status_code == 200:
                return resp.json()
            logger.warning("Turso pipeline error (%s): %s", resp.status_code, resp.text[:200])
    except Exception as exc:
        logger.warning("Failed communicating with Turso: %s", exc)
    return None


def execute_turso_sync(sql: str, args: Optional[List[Any]] = None) -> Optional[Dict[str, Any]]:
    """Synchronous execution against Turso HTTP Pipeline API (used in sync database hooks)."""
    if not is_turso_enabled():
        return None

    pipeline_url = _get_turso_http_url()
    headers = {
        "Authorization": f"Bearer {settings.TURSO_AUTH_TOKEN}",
        "Content-Type": "application/json",
    }
    stmt: Dict[str, Any] = {"sql": sql}
    if args:
        stmt["args"] = [_format_turso_arg(a) for a in args]

    payload = {
        "requests": [
            {"type": "execute", "stmt": stmt},
            {"type": "close"},
        ]
    }

    try:
        with httpx.Client(timeout=6.0) as client:
            resp = client.post(pipeline_url, headers=headers, json=payload)
            if resp.status_code == 200:
                return resp.json()
            logger.warning("Turso pipeline error (%s): %s", resp.status_code, resp.text[:200])
    except Exception as exc:
        logger.warning("Failed communicating with Turso: %s", exc)
    return None


def init_turso_schema() -> None:
    """Create all required tables in Turso if not already present."""
    if not is_turso_enabled():
        return

    statements = [
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
        """,
        """
        CREATE TABLE IF NOT EXISTS used_transactions (
            tx_hash TEXT PRIMARY KEY,
            endpoint TEXT NOT NULL,
            amount_usdc REAL NOT NULL,
            payer_address TEXT,
            verified_mode TEXT NOT NULL,
            created_at TEXT NOT NULL
        );
        """,
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
        """,
        """
        CREATE TABLE IF NOT EXISTS traffic_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            visitor_id TEXT NOT NULL DEFAULT '',
            path TEXT NOT NULL,
            method TEXT NOT NULL,
            status_code INTEGER NOT NULL,
            category TEXT NOT NULL,
            agent_type TEXT NOT NULL,
            country TEXT NOT NULL DEFAULT 'GLOBAL',
            latency_ms REAL NOT NULL DEFAULT 0.0,
            is_internal INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS checkout_failures (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            endpoint TEXT NOT NULL,
            failure_type TEXT NOT NULL,
            reason TEXT NOT NULL,
            payer_or_proof TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL
        );
        """,
    ]
    for sql in statements:
        execute_turso_sync(sql)


def _parse_turso_value(val_obj: Dict[str, Any]) -> Any:
    """Extract primitive Python value from Turso Hrana v2 value object."""
    if not isinstance(val_obj, dict):
        return val_obj
    vtype = val_obj.get("type", "null")
    if vtype == "null":
        return None
    if vtype == "integer":
        return int(val_obj.get("value", 0))
    if vtype == "float":
        return float(val_obj.get("value", 0.0))
    if vtype == "text":
        return str(val_obj.get("value", ""))
    if vtype == "blob":
        import base64
        return base64.b64decode(val_obj.get("base64", ""))
    return val_obj.get("value")


def hydrate_from_turso(db_path: Optional[str] = None) -> int:
    """Download historical records from Turso into local SQLite if local DB is fresh."""
    if not is_turso_enabled():
        return 0
    from app.database import get_connection

    # Check if local traffic_logs already has data
    with get_connection(db_path) as conn:
        local_count = conn.execute("SELECT COUNT(*) as c FROM traffic_logs WHERE is_internal = 0;").fetchone()["c"]
        if local_count >= 100:
            return 0

    res = execute_turso_sync(
        "SELECT visitor_id, path, method, status_code, category, agent_type, country, latency_ms, is_internal, created_at FROM traffic_logs ORDER BY id DESC LIMIT 500;"
    )
    if not res:
        return 0

    try:
        results = res.get("results", [])
        if not results:
            return 0
        result = results[0].get("response", {}).get("result", {})
        cols = [c["name"] for c in result.get("cols", [])]
        rows = result.get("rows", [])
        if not rows:
            return 0

        inserted = 0
        with get_connection(db_path) as conn:
            for r in rows:
                row_dict = {cols[i]: _parse_turso_value(r[i]) for i in range(len(cols))}
                conn.execute(
                    """
                    INSERT INTO traffic_logs
                    (visitor_id, path, method, status_code, category, agent_type, country, latency_ms, is_internal, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                    """,
                    (
                        row_dict.get("visitor_id", ""),
                        row_dict.get("path", ""),
                        row_dict.get("method", "GET"),
                        int(row_dict.get("status_code", 200)),
                        row_dict.get("category", "OTHER"),
                        row_dict.get("agent_type", "Bot"),
                        row_dict.get("country", "GLOBAL"),
                        float(row_dict.get("latency_ms", 0.0)),
                        int(row_dict.get("is_internal", 0)),
                        row_dict.get("created_at", ""),
                    ),
                )
                inserted += 1
            conn.commit()
        logger.info("Hydrated %d traffic logs from Turso into local DB", inserted)
        return inserted
    except Exception as exc:
        logger.warning("Hydration from Turso failed: %s", exc)
        return 0


