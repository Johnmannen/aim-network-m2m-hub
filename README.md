# ⚡ AIM Network — Autonomous M2M Data & Base DEX Intelligence Hub (`x402` + `MCP`)

[![Live Production](https://img.shields.io/badge/LIVE-johngarp.click-4ade80?style=for-the-badge)](https://johngarp.click)
[![x402 Protocol](https://img.shields.io/badge/Protocol-HTTP_402_(x402)-38bdf8?style=for-the-badge)](https://johngarp.click/agents.json)
[![Network](https://img.shields.io/badge/Network-Base_Mainnet_(USDC)-2563eb?style=for-the-badge)](https://johngarp.click/llms.txt)
[![MCP Ready](https://img.shields.io/badge/MCP-Compatible-7c3aed?style=for-the-badge)](https://johngarp.click/mcp)

**AIM Network** is an ultra-low-latency (`<150ms` cached) Machine-to-Machine (M2M) data and quantitative intelligence API built for autonomous trading bots, DeFi agents, and LLM frameworks.

* **Zero API Keys / Zero Signups:** Pay per call in **USDC on Base Mainnet (Chain ID 8453)** via the `HTTP 402 Payment Required` (`x402 v1.0`) standard.
* **Free Live Teaser:** Verify feed freshness and latency instantly at [`GET https://johngarp.click/api/v1/free-teaser`](https://johngarp.click/api/v1/free-teaser) (`$0.00 USDC`).
* **24-Hour VIP Pass (`$2.00 USDC`):** High-frequency bots can send `2.00 USDC` once and reuse the same `X-PAYMENT-PROOF` transaction hash for up to **1,000 calls across ALL endpoints for 24 hours**.

---

## 🔗 Live Discovery Manifests
- **LLM Manifest (`/llms.txt`):** [`https://johngarp.click/llms.txt`](https://johngarp.click/llms.txt)
- **x402 Agent Catalog (`/agents.json`):** [`https://johngarp.click/agents.json`](https://johngarp.click/agents.json)
- **MCP Tool Server (`/mcp`):** [`https://johngarp.click/mcp`](https://johngarp.click/mcp)
- **A2A Agent Card (`/.well-known/agent.json`):** [`https://johngarp.click/.well-known/agent.json`](https://johngarp.click/.well-known/agent.json)
- **OpenAPI / Swagger Docs (`/docs`):** [`https://johngarp.click/docs`](https://johngarp.click/docs)

---

## 📊 Available M2M Endpoints

| Endpoint | Price (Base USDC) | Description |
| :--- | :--- | :--- |
| `GET /api/v1/free-teaser` | **FREE (`0.00 USDC`)** | Instant BTC spot price & feed latency verification for autonomous agents. |
| `GET /api/v1/crypto-pulse` | **`0.01 USDC`** | Real-time BTC/ETH/SOL prices, 24h volumes, volatility index & Fear/Greed sentiment. |
| `GET /api/v1/base-dex-radar` | **`0.05 USDC`** | Live Base L2 DEX liquidity pools (Aerodrome/Uniswap), volume spikes & whale inflow radar. |
| `GET /api/v1/deep-market-report` | **`1.00 USDC`** | Institutional M2M quantitative market regime, Base L2 gas/slippage & actionable signals. |
| `GET /api/v1/trending/{slug}` | **`0.05 USDC`** | Auto-deployed trending narrative endpoints built hourly by the Autonomous Scout agent. |

---

## 🤖 3-Line Quickstart for AI Agents (Python)

```python
import httpx

# 1. Verify live feed for free ($0.00):
teaser = httpx.get("https://johngarp.click/api/v1/free-teaser").json()

# 2. Call any paid endpoint with your Base USDC transaction hash (or $2.00 24h VIP Pass hash):
resp = httpx.get(
    "https://johngarp.click/api/v1/base-dex-radar",
    headers={"X-PAYMENT-PROOF": "0x_YOUR_BASE_USDC_TX_HASH"}
)
print(resp.json())
```

### Payment Details (`x402 v1.0`)
- **Network:** `base-mainnet` (Chain ID `8453`)
- **Token:** `USDC` (`0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913`)
- **Recipient Wallet:** `0x1bbae07abebbb61f611391e02e81ee26b0c47b79`
