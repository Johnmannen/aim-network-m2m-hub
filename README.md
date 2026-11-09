# ⚡ AIM Network — Autonomous M2M Data & Base DEX Intelligence Hub (`x402 v2` + `MCP`)

[![Live Production](https://img.shields.io/badge/LIVE-johngarp.click-4ade80?style=for-the-badge)](https://johngarp.click)
[![x402 Protocol](https://img.shields.io/badge/Protocol-HTTP_402_(x402_v2)-38bdf8?style=for-the-badge)](https://johngarp.click/api/catalog)
[![Network](https://img.shields.io/badge/Network-Base_Mainnet_(USDC)-2563eb?style=for-the-badge)](https://johngarp.click/llms.txt)
[![MCP Ready](https://img.shields.io/badge/MCP-Compatible-7c3aed?style=for-the-badge)](https://johngarp.click/mcp)

**AIM Network** is an ultra-low-latency (`<150ms` cached) Machine-to-Machine (M2M) data and quantitative intelligence API built for autonomous trading bots, DeFi agents, and LLM frameworks.

* **Zero API Keys / Zero Signups:** Pay per call in **USDC on Base Mainnet (Chain ID 8453)** via the `HTTP 402 Payment Required` (`x402 v2.0`) standard with Base64 `PAYMENT-REQUIRED` and `PAYMENT-SIGNATURE` headers.
* **Full Machine Catalog:** Explore all routes and parameters at [`GET https://johngarp.click/api/catalog`](https://johngarp.click/api/catalog) (`$0.00 USDC`).
* **Free Live Teaser:** Verify feed freshness and latency instantly at [`GET https://johngarp.click/api/v1/free-teaser`](https://johngarp.click/api/v1/free-teaser) (`$0.00 USDC`).
* **24-Hour VIP Pass (`$1.50 USDC`):** High-frequency bots can send `1.50 USDC` once for **250 calls across all micro feeds for 24 hours**.

---

## 🔗 Live Discovery Manifests
- **Full API Catalog (`/api/catalog`):** [`https://johngarp.click/api/catalog`](https://johngarp.click/api/catalog)
- **x402 Discovery Card (`/.well-known/x402.json`):** [`https://johngarp.click/.well-known/x402.json`](https://johngarp.click/.well-known/x402.json)
- **LLM Manifest (`/llms.txt`):** [`https://johngarp.click/llms.txt`](https://johngarp.click/llms.txt)
- **x402 Agent Catalog (`/agents.json`):** [`https://johngarp.click/agents.json`](https://johngarp.click/agents.json)
- **MCP Tool Server (`/mcp`):** [`https://johngarp.click/mcp`](https://johngarp.click/mcp)
- **A2A Agent Card (`/.well-known/agent.json`):** [`https://johngarp.click/.well-known/agent.json`](https://johngarp.click/.well-known/agent.json)
- **OpenAPI / Swagger Docs (`/docs`):** [`https://johngarp.click/docs`](https://johngarp.click/docs)

---

## 📊 Available M2M Endpoints

| Endpoint | Price (Base USDC) | Base Units (6 dec) | Description |
| :--- | :--- | :--- | :--- |
| `GET /api/catalog` | **FREE (`0.00 USDC`)** | `0` | Complete machine-readable catalog of all active feeds & x402 v2 requirements. |
| `GET /api/v1/free-teaser` | **FREE (`0.00 USDC`)** | `0` | Instant BTC spot price & feed latency verification for autonomous agents. |
| `GET /api/v1/arb-scanner` | **`0.005 USDC`** | `5000` | Real-time cross-asset arbitrage, spread efficiency & Base L2 gas benchmarks. |
| `GET /api/v1/crypto-pulse` | **`0.005 USDC`** | `5000` | Real-time BTC/ETH/SOL prices, 24h volumes, volatility index & Fear/Greed sentiment. |
| `GET /api/v1/sentiment-signals` | **`0.020 USDC`** | `20000` | Multi-source quantitative market sentiment, orderflow & action signals. |
| `GET /api/v1/base-dex-radar` | **`0.020 USDC`** | `20000` | Live Base L2 DEX liquidity pools (Aerodrome/Uniswap), volume spikes & whale radar. |
| `GET /api/v1/quality/{slug}` | **`0.002 USDC`** | `2000` | Independent data quality, staleness, node consensus and integrity audit per asset. |
| `GET /api/v1/multi-source-dossier`| **`0.150 USDC`** | `150000` | Multi-source intelligence report, executive verdict & actionable bot directives. |
| `GET /api/v1/deep-market-report` | **`0.150 USDC`** | `150000` | Institutional M2M quantitative market regime, Base L2 gas/slippage & macro signals. |
| `GET /api/v1/trending/{slug}` | **`0.010 USDC`** | `10000` | Auto-deployed trending narrative endpoints built hourly by the Autonomous Scout agent. |

---

## 🤖 3-Line Quickstart for AI Agents (Python)

```python
import httpx

# 1. Verify live feed or inspect catalog for free ($0.00):
catalog = httpx.get("https://johngarp.click/api/catalog").json()

# 2. Call any paid endpoint via standard x402 v2 header:
resp = httpx.get(
    "https://johngarp.click/api/v1/arb-scanner",
    headers={"PAYMENT-SIGNATURE": "<BASE64_EIP3009_PAYMENT_SIGNATURE>"}
)
print(resp.json())
```

### Payment Details (`x402 v2.0`)
- **Network:** `eip155:8453` (Base Mainnet, Chain ID `8453`)
- **Token:** `USDC` (`0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913`)
- **Recipient Wallet:** `0x1bbae07abebbb61f611391e02e81ee26b0c47b79`

