"""
Autonomous Scout & Auto-Deployer Service (/cron/discover + Background Autopilot).
Scans live crypto/tech trending topics (via CoinGecko Trending API with resilient fallback),
synthesizes high-value M2M micro-API product proposals into SQLite discovery_logs,
AND automatically registers & deploys live payable endpoints under /api/v1/trending/{slug}.
"""

import re
from typing import Any, Dict, Optional
import httpx
from app.config import settings
from app.database import add_discovery_log, get_stats, register_dynamic_endpoint

FALLBACK_CANDIDATES = [
    ("Virtuals Protocol", "VIRTUAL", "virtual-protocol"),
    ("Aerodrome Finance", "AERO", "aerodrome-finance"),
    ("Bittensor", "TAO", "bittensor"),
    ("Render Network", "RENDER", "render-token"),
]


async def run_autonomous_scout(db_path: Optional[str] = None) -> Dict[str, Any]:
    """
    Query live market/search trends, log the discovery, AND auto-deploy a new
    live x402-protected API endpoint (/api/v1/trending/{slug}) if not already active.
    """
    existing_stats = get_stats(db_path)
    existing_slugs = {ep["slug"] for ep in existing_stats.get("dynamic_endpoints", [])}

    chosen_name = "Virtuals Protocol"
    chosen_symbol = "VIRTUAL"
    chosen_cg_id = "virtual-protocol"
    price_suggestion = settings.PRICE_DYNAMIC_USDC

    try:
        async with httpx.AsyncClient(timeout=3.5) as client:
            resp = await client.get("https://api.coingecko.com/api/v3/search/trending")
            if resp.status_code == 200:
                coins = resp.json().get("coins", [])
                for c in coins:
                    item = c.get("item", {})
                    sym = re.sub(r"[^a-z0-9]", "", item.get("symbol", "").lower())
                    if sym and sym not in existing_slugs:
                        chosen_name = item.get("name", chosen_name)
                        chosen_symbol = item.get("symbol", chosen_symbol).upper()
                        chosen_cg_id = item.get("id", chosen_cg_id)
                        break
    except Exception:
        pass

    slug = re.sub(r"[^a-z0-9]", "", chosen_symbol.lower()) or "virtual"
    if slug in existing_slugs:
        for fb_name, fb_sym, fb_id in FALLBACK_CANDIDATES:
            fb_slug = fb_sym.lower()
            if fb_slug not in existing_slugs:
                chosen_name, chosen_symbol, chosen_cg_id, slug = (
                    fb_name,
                    fb_sym,
                    fb_id,
                    fb_slug,
                )
                break

    # Auto-deploy live endpoint in SQLite
    deployed = register_dynamic_endpoint(
        slug=slug,
        asset_name=chosen_name,
        asset_symbol=chosen_symbol,
        coingecko_id=chosen_cg_id,
        price_usdc=price_suggestion,
        db_path=db_path,
    )

    endpoint_path = deployed["endpoint_path"]
    topic = f"Auto-Deployed Live API: {chosen_name} ({chosen_symbol}) Orderflow & Pulse"
    rationale = (
        f"Spanar-agenten identifierade hög efterfrågan på {chosen_name} ({chosen_symbol}) "
        f"och publicerade automatiskt {endpoint_path} (${price_suggestion:.2f} USDC via x402)."
    )

    logged = add_discovery_log(
        topic=topic,
        suggested_endpoint=endpoint_path,
        suggested_price_usdc=price_suggestion,
        rationale=rationale,
        status="LIVE_AUTO_DEPLOYED",
        db_path=db_path,
    )
    return {**logged, "deployed_endpoint": deployed}
