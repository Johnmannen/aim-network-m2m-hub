"""
Autonomous Scout Service (/cron/discover).
Scans live crypto/tech trending topics (via CoinGecko Trending API with resilient fallback)
and synthesizes high-value M2M micro-API product proposals into SQLite discovery_logs.
"""

from typing import Any, Dict, Optional
import httpx
from app.database import add_discovery_log


async def run_autonomous_scout(db_path: Optional[str] = None) -> Dict[str, Any]:
    """
    Query live market/search trends and propose a new M2M micro-API endpoint.
    """
    top_coin_name = "Virtuals Protocol / AI Agents"
    top_coin_symbol = "VIRTUAL"
    price_suggestion = 0.05

    try:
        async with httpx.AsyncClient(timeout=3.5) as client:
            resp = await client.get("https://api.coingecko.com/api/v3/search/trending")
            if resp.status_code == 200:
                coins = resp.json().get("coins", [])
                if coins:
                    item = coins[0].get("item", {})
                    top_coin_name = item.get("name", top_coin_name)
                    top_coin_symbol = item.get("symbol", top_coin_symbol).upper()
    except Exception:
        pass

    slug = top_coin_symbol.lower().replace(" ", "-")
    endpoint = f"/api/v1/trending-{slug}-pulse"
    topic = f"Live Trending Narrative: {top_coin_name} ({top_coin_symbol}) Orderflow & Sentiment"
    rationale = (
        f"Identifierad topp-trend bland autonoma trading-botar för {top_coin_name} ({top_coin_symbol}). "
        f"Rekommenderat x402-pris: ${price_suggestion:.2f} USDC/anrop."
    )

    logged = add_discovery_log(
        topic=topic,
        suggested_endpoint=endpoint,
        suggested_price_usdc=price_suggestion,
        rationale=rationale,
        status="READY_TO_BUILD",
        db_path=db_path,
    )
    return logged

