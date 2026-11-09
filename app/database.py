"""
SQLite Database Layer for AIM Network.
Handles persistent storage of:
- System state (ONLINE / PAUSED, call counters, USDC revenue)
- Used transaction hashes (Replay attack protection for x402 payments)
- Autonomous Scout discovery logs (New M2M API opportunities)
- Dynamic endpoints auto-deployed by the Scout
- 24h VIP Passes & Traffic/Conversion Radar telemetry
"""

import sqlite3
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any, Dict, Optional

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

        conn.execute(
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
            """
        )
        try:
            conn.execute("ALTER TABLE traffic_logs ADD COLUMN visitor_id TEXT NOT NULL DEFAULT '';")
        except Exception:
            pass

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS pin_failures (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                client_ip TEXT NOT NULL,
                failed_at REAL NOT NULL
            );
            """
        )

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS checkout_failures (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                endpoint TEXT NOT NULL,
                failure_type TEXT NOT NULL,
                reason TEXT NOT NULL,
                payer_or_proof TEXT NOT NULL DEFAULT '',
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

        cur = conn.execute("SELECT COUNT(*) as cnt FROM discovery_logs;")
        if cur.fetchone()["cnt"] == 0:
            conn.execute(
                """
                INSERT INTO discovery_logs (topic, suggested_endpoint, suggested_price_usdc, rationale, status, created_at)
                VALUES (?, ?, ?, ?, ?, ?);
                """,
                (
                    "Base L2 DEX Liquidity & Whale Inflows",
                    "/api/v1/base-dex-radar",
                    0.05,
                    "Hög efterfrågan från autonoma trading-botar på Base efter realtidsflöden i USDC-pooler.",
                    "LIVE_AUTO_DEPLOYED",
                    now,
                ),
            )
        conn.commit()


def get_stats(db_path: Optional[str] = None) -> Dict[str, Any]:
    """Return current system status, counters, recent transactions, scout logs, and traffic telemetry."""
    init_db(db_path)
    with get_connection(db_path) as conn:
        state_row = conn.execute("SELECT * FROM system_state WHERE id = 1;").fetchone()
        discoveries = conn.execute(
            "SELECT * FROM discovery_logs ORDER BY id DESC LIMIT 8;"
        ).fetchall()
        dynamic_eps = conn.execute(
            "SELECT * FROM dynamic_endpoints ORDER BY created_at DESC LIMIT 24;"
        ).fetchall()
        vip_rows = conn.execute(
            "SELECT * FROM vip_passes ORDER BY created_at DESC LIMIT 10;"
        ).fetchall()
        recent_txs = conn.execute(
            "SELECT * FROM used_transactions ORDER BY created_at DESC LIMIT 10;"
        ).fetchall()

        funnel_rows = conn.execute(
            """
            SELECT category, COUNT(*) as cnt
            FROM traffic_logs
            WHERE is_internal = 0
            GROUP BY category;
            """
        ).fetchall()
        funnel_map = {r["category"]: r["cnt"] for r in funnel_rows}

        avg_lat_row = conn.execute(
            "SELECT AVG(latency_ms) as avg_ms, COUNT(*) as total_req FROM traffic_logs WHERE is_internal = 0;"
        ).fetchone()

        agent_breakdown_rows = conn.execute(
            """
            SELECT agent_type, COUNT(*) as cnt
            FROM traffic_logs
            WHERE is_internal = 0
            GROUP BY agent_type
            ORDER BY cnt DESC
            LIMIT 6;
            """
        ).fetchall()

        endpoint_hits_rows = conn.execute(
            """
            SELECT path, COUNT(*) as cnt,
                   SUM(CASE WHEN status_code = 402 THEN 1 ELSE 0 END) as quotes_402,
                   SUM(CASE WHEN category = 'PAID_200' THEN 1 ELSE 0 END) as paid_200
            FROM traffic_logs
            WHERE is_internal = 0
            GROUP BY path
            ORDER BY cnt DESC
            LIMIT 8;
            """
        ).fetchall()

        recent_traffic_rows = conn.execute(
            """
            SELECT * FROM traffic_logs
            WHERE is_internal = 0
            ORDER BY id DESC
            LIMIT 15;
            """
        ).fetchall()

        fail_count_row = conn.execute(
            "SELECT COUNT(*) as cnt FROM checkout_failures;"
        ).fetchone()
        recent_failures_rows = conn.execute(
            "SELECT * FROM checkout_failures ORDER BY id DESC LIMIT 10;"
        ).fetchall()

        discovery_hits = int(funnel_map.get("DISCOVERY", 0)) + int(funnel_map.get("SAMPLE_200", 0))
        quotes_402 = int(funnel_map.get("QUOTE_402", 0))
        paid_200 = int(funnel_map.get("PAID_200", 0))
        payment_rejected_hits = max(
            int(funnel_map.get("PAYMENT_REJECTED", 0)),
            int(fail_count_row["cnt"] if fail_count_row else 0),
        )
        blocked_hits = int(funnel_map.get("BLOCKED", 0))
        scanner_hits = int(funnel_map.get("SCANNER", 0))
        total_external = int(avg_lat_row["total_req"] or 0)
        avg_latency_ms = round(float(avg_lat_row["avg_ms"] or 0.0), 1)
        conversion_pct = (
            round((paid_200 / quotes_402) * 100.0, 1)
            if quotes_402 > 0
            else (100.0 if paid_200 > 0 else 0.0)
        )

        return {
            "status": state_row["status"],
            "paused": bool(state_row["paused"]),
            "total_calls": int(state_row["calls_micro"] or 0) + int(state_row["calls_premium"] or 0),
            "calls_micro": state_row["calls_micro"],
            "calls_premium": state_row["calls_premium"],
            "revenue_usdc": round(float(state_row["revenue_usdc"]), 4),
            "updated_at": state_row["updated_at"],
            "discoveries": [dict(row) for row in discoveries],
            "dynamic_endpoints": [dict(row) for row in dynamic_eps],
            "vip_passes": [dict(row) for row in vip_rows],
            "recent_transactions": [dict(row) for row in recent_txs],
            "checkout_failures_count": int(fail_count_row["cnt"] if fail_count_row else 0),
            "recent_checkout_failures": [dict(row) for row in recent_failures_rows],
            "traffic_telemetry": {
                "total_external_requests": total_external,
                "discovery_hits": discovery_hits,
                "quotes_402": quotes_402,
                "paid_200": paid_200,
                "payment_rejected_hits": payment_rejected_hits,
                "blocked_hits": blocked_hits,
                "scanner_hits": scanner_hits,
                "conversion_rate_pct": conversion_pct,
                "avg_latency_ms": avg_latency_ms,
                "agent_breakdown": [dict(r) for r in agent_breakdown_rows],
                "endpoint_hits": [dict(r) for r in endpoint_hits_rows],
                "recent_stream": [dict(r) for r in recent_traffic_rows],
            },
        }


def record_checkout_failure(
    endpoint: str,
    failure_type: str,
    reason: str,
    payer_or_proof: str = "",
    db_path: Optional[str] = None,
) -> None:
    """Record an unfulfilled payment attempt or checkout error for admin diagnostics."""
    init_db(db_path)
    with get_connection(db_path) as conn:
        conn.execute(
            """
            INSERT INTO checkout_failures (endpoint, failure_type, reason, payer_or_proof, created_at)
            VALUES (?, ?, ?, ?, ?);
            """,
            (
                endpoint,
                failure_type,
                reason[:255],
                payer_or_proof[:120],
                datetime.now(timezone.utc).isoformat(),
            ),
        )
        conn.commit()


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
    amount_usdc: float | Decimal,
    tier: str = "micro",
    payer_address: str = "unknown",
    verified_mode: str = "onchain",
    db_path: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Atomically record a redeemed transaction hash and increment revenue & call stats.
    Raises ValueError if tx_hash was already used.
    """
    init_db(db_path)
    normalized = tx_hash.strip().lower()
    now = datetime.now(timezone.utc).isoformat()
    clean_amount = float(Decimal(str(amount_usdc)))

    with get_connection(db_path) as conn:
        try:
            conn.execute(
                """
                INSERT INTO used_transactions (tx_hash, endpoint, amount_usdc, payer_address, verified_mode, created_at)
                VALUES (?, ?, ?, ?, ?, ?);
                """,
                (
                    normalized,
                    endpoint,
                    clean_amount,
                    payer_address,
                    verified_mode,
                    now,
                ),
            )
        except sqlite3.IntegrityError as exc:
            raise ValueError(f"Transaction hash already used: {normalized}") from exc

        col = "calls_premium" if tier == "premium" else "calls_micro"
        conn.execute(
            f"""
            UPDATE system_state
            SET {col} = {col} + 1,
                revenue_usdc = ROUND(revenue_usdc + ?, 4),
                updated_at = ?
            WHERE id = 1;
            """,
            (clean_amount, now),
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
    suggested_price_usdc: float | Decimal,
    rationale: str,
    status: str = "QUEUED_FOR_AUTOPILOT",
    db_path: Optional[str] = None,
) -> Dict[str, Any]:
    """Insert a new autonomous scout API suggestion."""
    init_db(db_path)
    now = datetime.now(timezone.utc).isoformat()
    clean_price = float(Decimal(str(suggested_price_usdc)))
    with get_connection(db_path) as conn:
        cur = conn.execute(
            """
            INSERT INTO discovery_logs (topic, suggested_endpoint, suggested_price_usdc, rationale, status, created_at)
            VALUES (?, ?, ?, ?, ?, ?);
            """,
            (topic, suggested_endpoint, clean_price, rationale, status, now),
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
    price_usdc: float | Decimal = Decimal("0.05"),
    db_path: Optional[str] = None,
) -> Dict[str, Any]:
    """Register or return an auto-built dynamic M2M endpoint."""
    init_db(db_path)
    clean_slug = slug.lower().strip()
    endpoint_path = f"/api/v1/trending/{clean_slug}"
    now = datetime.now(timezone.utc).isoformat()
    clean_price = float(Decimal(str(price_usdc)))
    with get_connection(db_path) as conn:
        conn.execute(
            """
            INSERT OR IGNORE INTO dynamic_endpoints
            (slug, endpoint_path, asset_name, asset_symbol, coingecko_id, price_usdc, calls_count, revenue_usdc, created_at)
            VALUES (?, ?, ?, ?, ?, ?, 0, 0.0, ?);
            """,
            (
                clean_slug,
                endpoint_path,
                asset_name,
                asset_symbol,
                coingecko_id,
                clean_price,
                now,
            ),
        )
        # Prune oldest unused scout endpoints if exceeding 12 items (never delete active ones or canonical/bootstrapped slugs)
        conn.execute(
            """
            DELETE FROM dynamic_endpoints
            WHERE calls_count = 0
              AND slug NOT IN ('morpho', 'virtual', 'wasted')
              AND slug NOT IN (
                  SELECT slug FROM dynamic_endpoints
                  WHERE slug NOT IN ('morpho', 'virtual', 'wasted')
                  ORDER BY created_at DESC LIMIT 12
              );
            """
        )
        conn.commit()
        row = conn.execute(
            "SELECT * FROM dynamic_endpoints WHERE slug = ?;", (clean_slug,)
        ).fetchone()
        return dict(row)


def increment_dynamic_endpoint_stats(
    slug: str, amount_usdc: float | Decimal, db_path: Optional[str] = None
) -> None:
    """Increment call counter and revenue on a specific dynamic endpoint."""
    init_db(db_path)
    clean_amount = float(Decimal(str(amount_usdc)))
    clean_slug = slug.lower().strip()
    with get_connection(db_path) as conn:
        cursor = conn.execute(
            """
            UPDATE dynamic_endpoints
            SET calls_count = calls_count + 1,
                revenue_usdc = ROUND(revenue_usdc + ?, 4)
            WHERE slug = ?;
            """,
            (clean_amount, clean_slug),
        )
        if cursor.rowcount == 0:
            # Canonical trending slugs are defined in code, not seeded in this table.
            # Upsert keeps their call/revenue telemetry countable instead of silently lost.
            from app.services.market_data import CANONICAL_TRENDING_ENDPOINTS

            canonical_meta = next(
                (item for item in CANONICAL_TRENDING_ENDPOINTS if item["slug"] == clean_slug),
                None,
            )
            asset_name = canonical_meta["asset_name"] if canonical_meta else clean_slug.capitalize()
            asset_symbol = canonical_meta["asset_symbol"] if canonical_meta else clean_slug.upper()
            conn.execute(
                """
                INSERT INTO dynamic_endpoints
                (slug, endpoint_path, asset_name, asset_symbol, coingecko_id,
                 price_usdc, calls_count, revenue_usdc, created_at)
                VALUES (?, ?, ?, ?, ?, ?, 1, ?, ?);
                """,
                (
                    clean_slug,
                    f"/api/v1/trending/{clean_slug}",
                    asset_name,
                    asset_symbol,
                    clean_slug,
                    clean_amount,
                    clean_amount,
                    datetime.now(timezone.utc).isoformat(),
                ),
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

        # Margin Protection: Welcome Bonus (0.0) and Micro VIP passes below the Pro
        # price apply only to micro ($0.01-$0.05) and dynamic_scout tiers.
        # Premium tier ($1.00 Deep Market Report) requires a Pro Pass or standard payment.
        if tier == "premium" and float(row["amount_usdc"]) < float(
            settings.PRO_PASS_PRICE_DEC
        ):
            return None

        conn.execute(
            "UPDATE vip_passes SET calls_used = calls_used + 1 WHERE tx_hash = ?;",
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


def get_vip_pass(
    tx_hash: str, db_path: Optional[str] = None
) -> Optional[Dict[str, Any]]:
    """Retrieve an existing VIP pass record by tx_hash without modifying call count."""
    init_db(db_path)
    normalized = tx_hash.strip().lower()
    with get_connection(db_path) as conn:
        row = conn.execute(
            "SELECT * FROM vip_passes WHERE tx_hash = ?;", (normalized,)
        ).fetchone()
        if not row:
            return None
        d = dict(row)
        d["tier"] = (
            "pro"
            if float(d["amount_usdc"]) >= float(settings.PRO_PASS_PRICE_DEC)
            else "micro"
        )
        return d


def create_vip_pass(
    tx_hash: str,
    amount_usdc: float | Decimal,
    payer_address: str = "unknown",
    tier: str = "premium",
    verified_mode: str = "onchain_vip",
    db_path: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Create a 24h VIP Pass (500 calls for Micro, 50 calls for Pro) and record initial revenue.
    Raises ValueError if tx_hash was already redeemed.
    """
    init_db(db_path)
    normalized = tx_hash.strip().lower()
    now_dt = datetime.now(timezone.utc)
    now_iso = now_dt.isoformat()
    clean_amount = float(Decimal(str(amount_usdc)))
    is_pro = clean_amount >= float(settings.PRO_PASS_PRICE_DEC) or str(tier).lower() in (
        "pro",
        "premium_pro",
    )
    pass_tier = "pro" if is_pro else "micro"
    max_quota = settings.PRO_PASS_MAX_CALLS if is_pro else settings.VIP_PASS_MAX_CALLS
    duration_hours = settings.PRO_PASS_DURATION_HOURS if is_pro else settings.VIP_PASS_DURATION_HOURS
    expires_iso = (
        now_dt + timedelta(hours=duration_hours)
    ).isoformat()

    record_paid_call(
        tx_hash=normalized,
        endpoint="/api/v1/vip-24h-pass",
        amount_usdc=clean_amount,
        tier=pass_tier,
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
                clean_amount,
                max_quota,
                expires_iso,
                now_iso,
            ),
        )
        conn.commit()
        row = conn.execute(
            "SELECT * FROM vip_passes WHERE tx_hash = ?;", (normalized,)
        ).fetchone()
        result = dict(row)
        result["tier"] = pass_tier
        return result


def is_first_time_buyer(payer_address: str, db_path: Optional[str] = None) -> bool:
    """Check if this is the very first purchase recorded for this payer address."""
    if not payer_address or payer_address.lower() in ("unknown", ""):
        return False
    init_db(db_path)
    with get_connection(db_path) as conn:
        row = conn.execute(
            "SELECT count(*) as count FROM used_transactions WHERE lower(payer_address) = ?;",
            (payer_address.lower().strip(),),
        ).fetchone()
        return bool(row and int(row["count"]) == 1)


def grant_welcome_bonus_pass(
    tx_hash: str,
    payer_address: str,
    bonus_calls: int = 5,
    duration_hours: int = 24,
    db_path: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """
    Sybil-resistant onboarding reward:
    Grants a first-time buyer a Welcome Bonus VIP Pass for `bonus_calls` free calls
    across all endpoints over the next `duration_hours` using the same transaction hash.
    """
    init_db(db_path)
    normalized = tx_hash.strip().lower()
    now_dt = datetime.now(timezone.utc)
    now_iso = now_dt.isoformat()
    expires_iso = (now_dt + timedelta(hours=duration_hours)).isoformat()

    with get_connection(db_path) as conn:
        existing = conn.execute(
            "SELECT * FROM vip_passes WHERE tx_hash = ?;", (normalized,)
        ).fetchone()
        if existing:
            return None
        conn.execute(
            """
            INSERT INTO vip_passes
            (tx_hash, payer_address, amount_usdc, calls_used, max_calls, expires_at, created_at)
            VALUES (?, ?, 0.0, 1, ?, ?, ?);
            """,
            (
                normalized,
                payer_address.lower().strip(),
                1 + bonus_calls,
                expires_iso,
                now_iso,
            ),
        )
        conn.commit()
        row = conn.execute(
            "SELECT * FROM vip_passes WHERE tx_hash = ?;", (normalized,)
        ).fetchone()
        result = dict(row)
        result["tier"] = "micro"
        return result


def classify_user_agent(user_agent: str) -> str:
    """Classify visitor into human-readable AI Bot / SDK / Crawler / Browser category."""
    ua = (user_agent or "").lower()
    if not ua:
        return "🤖 Unknown M2M Agent"
    if "gptbot" in ua or "openai" in ua or "chatgpt" in ua:
        return "🧠 OpenAI / GPTBot"
    if "claude" in ua or "anthropic" in ua:
        return "🧠 Anthropic / ClaudeBot"
    if "perplexity" in ua:
        return "🔎 Perplexity AI Bot"
    if "googlebot" in ua or "gemini" in ua or "google-extended" in ua:
        return "🔎 Google / Gemini Crawler"
    if "mcp" in ua or "smithery" in ua or "glama" in ua:
        return "🔌 MCP Client / Directory"
    if "httpx" in ua or "python-requests" in ua or "aiohttp" in ua:
        return "🐍 Python AI/Trading Bot"
    if "axios" in ua or "node" in ua or "undici" in ua or "got" in ua:
        return "⚡ Node.js / TS Agent"
    if "curl" in ua:
        return "💻 CLI / Keep-Alive Ping"
    if "mozilla" in ua or "chrome" in ua or "safari" in ua:
        return "🌐 Web Browser (Human)"
    return f"🤖 Custom Bot ({user_agent[:18]})"


def log_traffic_event(
    path: str,
    method: str,
    status_code: int,
    user_agent: str = "",
    country: str = "GLOBAL",
    latency_ms: float = 0.0,
    has_admin_cookie: bool = False,
    is_sample: bool = False,
    payment_attempt: bool = False,
    client_ip: str = "",
    db_path: Optional[str] = None,
) -> None:
    """Record an HTTP request into traffic_logs with automatic funnel categorization and visitor tracking."""
    init_db(db_path)

    ua_lower = (user_agent or "").lower()
    path_lower = path.lower()
    is_internal = (
        1
        if (
            path in ("/admin", "/health", "/favicon.ico")
            or path.startswith("/api/admin")
            or "aim-keepalive" in ua_lower
            or "aim-internal-probe" in ua_lower
            or "aim-dashboard" in ua_lower
            or has_admin_cookie
        )
        else 0
    )

    # Skip logging repetitive 200 OK internal admin polls or health checks into traffic_logs
    if is_internal and status_code == 200 and path in ("/admin", "/health", "/favicon.ico"):
        return

    is_scanner = (
        path_lower.endswith((".php", ".asp", ".aspx", ".jsp"))
        or any(s in path_lower for s in ("/wp-", "/.svn", "/.git", "/.env", "/.hg", "/hellopress"))
    )

    if status_code == 402:
        category = "PAYMENT_REJECTED" if payment_attempt else "QUOTE_402"
    elif is_scanner:
        category = "SCANNER"
    elif status_code in (401, 403, 429, 503):
        category = "BLOCKED"
    elif is_sample or "sample=true" in path_lower or "sample=1" in path_lower:
        category = "SAMPLE_200"
    elif (
        path.startswith("/api/v1/")
        and path != "/api/v1/free-teaser"
        and status_code == 200
    ):
        category = "PAID_200"
    elif path in (
        "/",
        "/llms.txt",
        "/agents.json",
        "/.well-known/agent.json",
        "/.well-known/glama.json",
        "/mcp/.well-known/glama.json",
        "/mcp",
        "/openapi.json",
        "/docs",
        "/sitemap.xml",
        "/robots.txt",
        "/api/v1/free-teaser",
        "/api/catalog",
        "/catalog",
        "/.well-known/x402.json",
        "/.well-known/x402",
    ):
        category = "DISCOVERY"
    else:
        category = "OTHER"

    if is_scanner:
        agent_label = "🔍 Vulnerability Scanner"
    elif "glama" in ua_lower or "smithery" in ua_lower or (path == "/mcp" and "node" in ua_lower):
        agent_label = "🌐 MCP Directory (Glama)"
    elif "simulerad test-bot" in (user_agent or "").lower():
        agent_label = "🧪 Simulerad Test-Bot (Admin)"
    else:
        agent_label = classify_user_agent(user_agent)

    import hashlib
    raw_fp = f"{client_ip}_{user_agent}".strip()
    fp_hash = hashlib.sha256(raw_fp.encode("utf-8", errors="ignore")).hexdigest()[:6]
    if "claude" in ua_lower:
        prefix = "claude"
    elif "gpt" in ua_lower or "openai" in ua_lower:
        prefix = "openai"
    elif "perplexity" in ua_lower:
        prefix = "perplexity"
    elif "gemini" in ua_lower or "google" in ua_lower:
        prefix = "gemini"
    elif "python" in ua_lower or "httpx" in ua_lower:
        prefix = "python"
    elif "curl" in ua_lower:
        prefix = "curl"
    elif is_scanner:
        prefix = "scan"
    else:
        prefix = "bot"
    visitor_id = f"{prefix}_{fp_hash}"

    now_dt = datetime.now(timezone.utc)
    now_iso = now_dt.isoformat()
    retention_days = int(getattr(settings, "TRAFFIC_RETENTION_DAYS", 30))
    cutoff_iso = (now_dt - timedelta(days=retention_days)).isoformat()

    with get_connection(db_path) as conn:
        conn.execute(
            """
            INSERT INTO traffic_logs
            (visitor_id, path, method, status_code, category, agent_type, country, latency_ms, is_internal, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """,
            (
                visitor_id,
                path,
                method.upper(),
                int(status_code),
                category,
                agent_label,
                (country or "GLOBAL").upper()[:8],
                round(float(latency_ms), 2),
                is_internal,
                now_iso,
            ),
        )
        conn.execute(
            """
            DELETE FROM traffic_logs
            WHERE created_at < ? OR id NOT IN (
                SELECT id FROM traffic_logs ORDER BY id DESC LIMIT 5000
            );
            """,
            (cutoff_iso,),
        )
        conn.commit()

    # Sync to Turso Cloud SQLite if enabled
    try:
        from app.services.turso_sync import execute_turso_sync, is_turso_enabled
        if is_turso_enabled() and not is_internal:
            execute_turso_sync(
                """
                INSERT INTO traffic_logs
                (visitor_id, path, method, status_code, category, agent_type, country, latency_ms, is_internal, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                """,
                [
                    visitor_id,
                    path,
                    method.upper(),
                    int(status_code),
                    category,
                    agent_label,
                    (country or "GLOBAL").upper()[:8],
                    round(float(latency_ms), 2),
                    is_internal,
                    now_iso,
                ],
            )
    except Exception as exc:
        logger.warning("Turso traffic sync skipped: %s", exc)


def get_paginated_traffic_logs(
    search: str = "",
    filter_cat: str = "ALL",
    page: int = 1,
    page_size: int = 100,
    db_path: Optional[str] = None,
) -> Dict[str, Any]:
    """Retrieve filtered, paginated traffic logs with visitor session tracking."""
    init_db(db_path)
    clean_search = (search or "").strip().lower()
    clean_filter = (filter_cat or "ALL").upper()
    offset = max(0, (page - 1) * page_size)

    where_clauses = ["is_internal = 0"]
    params: list[Any] = []

    if clean_search:
        where_clauses.append(
            "(LOWER(path) LIKE ? OR LOWER(agent_type) LIKE ? OR LOWER(country) LIKE ? OR LOWER(visitor_id) LIKE ?)"
        )
        s_param = f"%{clean_search}%"
        params.extend([s_param, s_param, s_param, s_param])

    if clean_filter == "PAID":
        where_clauses.append("category = 'PAID_200'")
    elif clean_filter == "QUOTE":
        where_clauses.append("status_code = 402 AND category != 'PAYMENT_REJECTED'")
    elif clean_filter == "REJECT":
        where_clauses.append("category = 'PAYMENT_REJECTED'")
    elif clean_filter == "BOTS":
        where_clauses.append("agent_type NOT LIKE '%Browser%'")

    where_sql = " AND ".join(where_clauses)

    with get_connection(db_path) as conn:
        count_query = f"SELECT COUNT(*) as total FROM traffic_logs WHERE {where_sql};"
        total_items = conn.execute(count_query, params).fetchone()["total"]

        query = f"""
            SELECT * FROM traffic_logs
            WHERE {where_sql}
            ORDER BY id DESC
            LIMIT ? OFFSET ?;
        """
        rows = conn.execute(query, params + [page_size, offset]).fetchall()
        total_pages = max(1, (total_items + page_size - 1) // page_size)

        return {
            "records": [dict(r) for r in rows],
            "total_items": total_items,
            "page": page,
            "page_size": page_size,
            "total_pages": total_pages,
            "search": search,
            "filter": clean_filter,
        }


def get_visitor_journey(visitor_id: str, db_path: Optional[str] = None) -> list[dict[str, Any]]:
    """Retrieve full chronological clickstream/journey for an individual bot or visitor."""
    init_db(db_path)
    clean_id = (visitor_id or "").strip()
    if not clean_id:
        return []
    with get_connection(db_path) as conn:
        rows = conn.execute(
            """
            SELECT * FROM traffic_logs
            WHERE visitor_id = ?
            ORDER BY id ASC;
            """,
            (clean_id,),
        ).fetchall()
        return [dict(r) for r in rows]


def export_db_snapshot(db_path: Optional[str] = None) -> Dict[str, Any]:
    """
    Export SQLite state for persistent cloud backup.
    Includes used_transactions (replay protection), vip_passes, dynamic_endpoints,
    discovery_logs, and anonymized traffic_logs.
    """
    init_db(db_path)
    with get_connection(db_path) as conn:
        state_row = conn.execute("SELECT * FROM system_state WHERE id = 1;").fetchone()
        used_txs = conn.execute("SELECT * FROM used_transactions;").fetchall()
        discoveries = conn.execute("SELECT * FROM discovery_logs;").fetchall()
        dyn_eps = conn.execute("SELECT * FROM dynamic_endpoints;").fetchall()
        vip_rows = conn.execute("SELECT * FROM vip_passes;").fetchall()
        traffic_rows = conn.execute(
            "SELECT * FROM traffic_logs ORDER BY id DESC LIMIT 1000;"
        ).fetchall()

        return {
            "snapshot_version": "1.1",
            "exported_at": datetime.now(timezone.utc).isoformat(),
            "system_state": dict(state_row) if state_row else {},
            "used_transactions": [
                {**dict(r), "payer_address": "redacted"} for r in used_txs
            ],
            "discovery_logs": [dict(r) for r in discoveries],
            "dynamic_endpoints": [dict(r) for r in dyn_eps],
            "vip_passes": [
                {**dict(r), "payer_address": "redacted"} for r in vip_rows
            ],
            "traffic_logs": [
                {**dict(r), "client_ip": "redacted"} for r in reversed(traffic_rows)
            ],
        }


def import_db_snapshot(
    snapshot: Dict[str, Any], db_path: Optional[str] = None
) -> Dict[str, Any]:
    """
    Idempotently merge a cloud backup snapshot into SQLite on container startup.
    Never deletes existing rows; only inserts missing transactions, endpoints, and logs.
    """
    init_db(db_path)
    with get_connection(db_path) as conn:
        st = snapshot.get("system_state") or {}
        if st:
            cur_st = conn.execute(
                "SELECT * FROM system_state WHERE id = 1;"
            ).fetchone()
            new_micro = max(int(cur_st["calls_micro"]), int(st.get("calls_micro", 0)))
            new_prem = max(
                int(cur_st["calls_premium"]), int(st.get("calls_premium", 0))
            )
            new_rev = max(
                float(cur_st["revenue_usdc"]), float(st.get("revenue_usdc", 0.0))
            )
            conn.execute(
                """
                UPDATE system_state
                SET calls_micro = ?, calls_premium = ?, revenue_usdc = ?
                WHERE id = 1;
                """,
                (new_micro, new_prem, new_rev),
            )

        for tx in snapshot.get("used_transactions", []):
            conn.execute(
                """
                INSERT OR IGNORE INTO used_transactions
                (tx_hash, endpoint, amount_usdc, payer_address, verified_mode, created_at)
                VALUES (?, ?, ?, ?, ?, ?);
                """,
                (
                    tx["tx_hash"],
                    tx["endpoint"],
                    tx["amount_usdc"],
                    tx.get("payer_address", "redacted"),
                    tx.get("verified_mode", "onchain"),
                    tx["created_at"],
                ),
            )

        for ep in snapshot.get("dynamic_endpoints", []):
            conn.execute(
                """
                INSERT OR IGNORE INTO dynamic_endpoints
                (slug, endpoint_path, asset_name, asset_symbol, coingecko_id, price_usdc, calls_count, revenue_usdc, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);
                """,
                (
                    ep["slug"],
                    ep["endpoint_path"],
                    ep["asset_name"],
                    ep["asset_symbol"],
                    ep["coingecko_id"],
                    ep["price_usdc"],
                    ep.get("calls_count", 0),
                    ep.get("revenue_usdc", 0.0),
                    ep["created_at"],
                ),
            )

        for vp in snapshot.get("vip_passes", []):
            conn.execute(
                """
                INSERT OR IGNORE INTO vip_passes
                (tx_hash, payer_address, amount_usdc, calls_used, max_calls, expires_at, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?);
                """,
                (
                    vp["tx_hash"],
                    vp.get("payer_address", "redacted"),
                    vp["amount_usdc"],
                    vp.get("calls_used", 0),
                    vp.get("max_calls", 1000),
                    vp["expires_at"],
                    vp["created_at"],
                ),
            )

        cur_cnt = conn.execute(
            "SELECT COUNT(*) as c FROM traffic_logs WHERE is_internal = 0;"
        ).fetchone()["c"]
        snap_traffic = snapshot.get("traffic_logs", [])
        if cur_cnt == 0 and snap_traffic:
            for tr in snap_traffic:
                conn.execute(
                    """
                    INSERT INTO traffic_logs
                    (path, method, status_code, category, agent_type, country, latency_ms, is_internal, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);
                    """,
                    (
                        tr["path"],
                        tr["method"],
                        tr["status_code"],
                        tr["category"],
                        tr["agent_type"],
                        tr.get("country", "GLOBAL"),
                        tr.get("latency_ms", 0.0),
                        tr.get("is_internal", 0),
                        tr["created_at"],
                    ),
                )
        conn.commit()
    return get_stats(db_path)


def check_pin_lockout_db(
    client_ip: str,
    window_seconds: int = 900,
    max_failures: int = 5,
    db_path: Optional[str] = None,
) -> bool:
    """Return True if client_ip has >= max_failures in the last window_seconds (persisted in SQLite)."""
    import time as _time

    init_db(db_path)
    cutoff = _time.time() - window_seconds
    with get_connection(db_path) as conn:
        conn.execute("DELETE FROM pin_failures WHERE failed_at < ?;", (cutoff,))
        cnt = conn.execute(
            "SELECT COUNT(*) as c FROM pin_failures WHERE client_ip = ?;",
            (client_ip,),
        ).fetchone()["c"]
        conn.commit()
        return int(cnt) >= max_failures


def record_pin_failure_db(client_ip: str, db_path: Optional[str] = None) -> None:
    """Persist a failed PIN/token attempt in SQLite."""
    import time as _time

    init_db(db_path)
    with get_connection(db_path) as conn:
        conn.execute(
            "INSERT INTO pin_failures (client_ip, failed_at) VALUES (?, ?);",
            (client_ip, _time.time()),
        )
        conn.commit()


def clear_pin_failures_db(
    client_ip: Optional[str] = None, db_path: Optional[str] = None
) -> None:
    """Clear failed PIN attempts for client_ip (or all if client_ip is None)."""
    init_db(db_path)
    with get_connection(db_path) as conn:
        if client_ip is None:
            conn.execute("DELETE FROM pin_failures;")
        else:
            conn.execute("DELETE FROM pin_failures WHERE client_ip = ?;", (client_ip,))
        conn.commit()


def reset_simulated_purchases(db_path: Optional[str] = None) -> Dict[str, Any]:
    """
    Remove all admin-simulated test purchases (verified_mode == 'admin_simulation')
    and recalculate system_state counters from real transactions only.
    """
    init_db(db_path)
    now = datetime.now(timezone.utc).isoformat()
    with get_connection(db_path) as conn:
        conn.execute(
            "DELETE FROM used_transactions WHERE verified_mode = 'admin_simulation';"
        )
        conn.execute(
            "DELETE FROM traffic_logs WHERE agent_type LIKE '%Simulerad Test-Bot%';"
        )
        micro_cnt = conn.execute(
            """
            SELECT COUNT(*) as c FROM used_transactions
            WHERE amount_usdc < 0.50;
            """
        ).fetchone()["c"]
        prem_cnt = conn.execute(
            """
            SELECT COUNT(*) as c FROM used_transactions
            WHERE amount_usdc >= 0.50;
            """
        ).fetchone()["c"]
        total_rev = conn.execute(
            "SELECT COALESCE(SUM(amount_usdc), 0.0) as s FROM used_transactions;"
        ).fetchone()["s"]
        conn.execute(
            """
            UPDATE system_state
            SET calls_micro = ?, calls_premium = ?, revenue_usdc = ROUND(?, 4), updated_at = ?
            WHERE id = 1;
            """,
            (int(micro_cnt), int(prem_cnt), float(total_rev), now),
        )
        conn.commit()
    return get_stats(db_path)


def clear_traffic_logs_db(db_path: Optional[str] = None) -> Dict[str, Any]:
    """Clear all rows in traffic_logs (preserving real transactions and revenue)."""
    init_db(db_path)
    with get_connection(db_path) as conn:
        conn.execute("DELETE FROM traffic_logs;")
        conn.commit()
    return get_stats(db_path)
