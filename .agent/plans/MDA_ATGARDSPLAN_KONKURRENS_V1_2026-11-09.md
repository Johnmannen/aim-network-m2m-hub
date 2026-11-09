# 📋 AIM Network — Master-Åtgärdsplan & Intäktsstrategi (V2.1 Fast Track)
## Syntes av Konkurrensanalys, Gemini Deep Research & Verifierad Infrastruktur

**Dokumentversion:** V2.2 (Pass 1 Driftsatt & Verifierad live, Infrastruktur Klar)  
**Datum:** 2026-11-09  
**Källunderlag:**
1. `Konkurrensanalys AIM Network.md` (Intern revision, Base L2-nisch, proveniens, kvalitet).
2. `Gemini Deep Research` (Marknadskartläggning över 78 267 endpoints, 2-centsregeln, 79 %-fällan).
3. `Trafikanalys 2026-11-08` + Live Cloudflare & UptimeRobot-verifiering (9 nov 2026).
**Tillämpade Skills:** `project-planner` & `writing-plans`  
**Status:** Pass 1 genomfört & driftsatt på Render! Nästa: Pass 2 (Skarp testbetalning) & Pass 3 (Katalogregistreringar)  

---

## 1. Verifierad Infrastrukturstatus (Slår 79 % av konkurrenterna REDAN IDAG)

Bildbevis och historiska artifacts bekräftar att **Infrastruktursteget (f.d. Pass 2) redan är 100 % genomfört och aktivt**:

```
[VERIFIERAD SKYDDSSTATUS: JOHNGARP.CLICK]
 ├── ✅ Cloudflare Bot Fight Mode: AVSTÄNGT (OFF) — Släpper igenom curl, python-httpx och autonoma botar.
 ├── ✅ Cloudflare AI Labyrinth: AVSTÄNGT (OFF).
 ├── ✅ Cloudflare AI Crawler & Agent Access Policies: AKTIVT "Allow (do not block)"
 │     ├── Search Bots: Allow
 │     ├── Training Crawlers: Allow
 │     ├── Agents: Allow
 │     └── Personal Agents (Claude Duet, OpenAI dots, Gemini Spark, Meta Muse): Allow
 └── ✅ Render Insomningsskydd (Keepalive): AKTIVT via UptimeRobot (5-minuters intervall)
       └── Render-instansen somnar aldrig. Konstant responstid och noll kallstart.
```

> **Slutsats:** `johngarp.click` har redan undvikit "79 %-fällan" på nätverksnivå. Servern är vaken dygnet runt och Cloudflare släpper igenom autonoma agenter. Den enda kvarvarande anledningen till 0 köp är nu enbart **koden (x402 v2-headers), prissättningen och distributionen**.

---

## 2. Den Reviderade Pris- & Produktstrukturen

Alla priser är i USDC på Base Mainnet (`eip155:8453`, token `0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913`).

| Tjänst / Endpoint | Nytt Pris | Base Units (6 dec) | Konkurrentjämförelse & Mervärde |
| :--- | :--- | :--- | :--- |
| **`/api/catalog`** | **0,00 USDC** | `0` | **Gratis katalogruta.** 75,3 % av konkurrenterna saknar detta. Gör att katalog-botar (TOLL·402, api-402) direkt godkänner och indexerar oss. |
| **`/api/v1/arb-scanner`** *(el. `crypto-pulse`)* | **0,005 USDC** | `5000` | **Volym-tjänst.** Matchar CoinGeckos nya låga pris (0,005), slår CoinMarketCap (0,01). Ger spread och momentum. |
| **`/api/v1/sentiment-signals`** *(el. `radar`)* | **0,020 USDC** | `20000` | **Mellan-tjänst.** Exakt på marknadens medianpris (20 öre). Strukturerade Köp/Sälj/Neutral-signaler för trading-botar. |
| **`/api/v1/multi-source-dossier`** *(f.d. `deep-market-report`)* | **0,150 USDC** | `150000` | **Premium-analys.** Sänkt från $1.00 till 0,15 USDC (1,50 kr). Flerstegs-rapport som sparar boten dyra AI-tokens. |
| **`/api/v1/quality/{slug}`** *(Vår Moat)* | **0,002 USDC** | `2000` | **Dataintegritet & Färshetsbevis.** Ingen konkurrent säljer osäkerhets- och kvalitetsmetrik separat. |
| **`VIP-Pass (24h)`** | **$1.50 USDC** | `1500000` | **250 anrop.** Snittpris 0,006 USDC/anrop. Harmonisera kod och dokumentation så att 1 000 vs 500 diskrepansen försvinner. |
| **`Gratis Teaser / Kvot`** | **0,00 USDC** | `0` | **100 fria anrop/dygn** med krav på attribution (`"Source": "AIM Network"`) för att bygga telemetri och trafik. |

---

## 3. Komprimerad Exekveringsplan (Endast 3 Kvarvarande Pass)

Eftersom infrastrukturen redan är klar krymper den faktiska arbetstiden till **ca 2.5 – 3 timmar**:

```
KVARVARANDE EXEKVERINGSPASS (FAST TRACK)
┌────────────────────────────────────────────────────────────────────────┐
│ PASS 1: KODUPPGRATERING TILL x402 V2 & NYA ENDPOINTS (ca 1.5 – 2h)    │
│  - Garantera Base64 `PAYMENT-REQUIRED` & `PAYMENT-SIGNATURE`           │
│  - Implementera /api/catalog & nya prissteg (0.005, 0.02, 0.15 USDC)   │
│  - Säkra SQLite-persistens och PIN-lås för /admin med probe-räknare    │
│  - Uppdatera llms.txt, agents.json, x402.json                          │
├────────────────────────────────────────────────────────────────────────┤
│ [PASS 2]: INFRASTRUKTUR & KEEPALIVE ──> ✅ REDAN KLART & VERIFIERAT!   │
│  - Cloudflare Bot Fight Mode: AVSTÄNGT                                 │
│  - Cloudflare AI Agent Access Policies: ALLOW (DO NOT BLOCK)           │
│  - UptimeRobot: Aktivt med 5-minuters ping                             │
├────────────────────────────────────────────────────────────────────────┤
│ PASS 2 (f.d. 3): SKARP TESTBETALNING PÅ BASE MAINNET (ca 30 min)       │
│  - Utför 1 skarpt x402-köp med testskript mot 0.005 USDC-endpointen    │
│  - Verifiera att 200 OK + PAYMENT-RESPONSE genereras och loggas        │
├────────────────────────────────────────────────────────────────────────┤
│ PASS 3 (f.d. 4): REGISTRERING I DE 6 MARKNADSPLATSERNA (ca 45 min)     │
│  - x402apis.io, relai.fi/market, 402.com.tr / api-402.com              │
│  - Coinbase Bazaar (CDP), x402scan, Glama.ai                           │
│  - Lägg till GitHub-ämnestaggar (x402, mcp-server, base-usdc)          │
└────────────────────────────────────────────────────────────────────────┘
```

---

### Detaljerad Genomgång av Kvarvarande Pass

#### ⚡ PASS 1: Koduppgradering till x402 v2 & Nya Endpoints (Arbetstid: ~1.5–2h)
1. **x402 v2 Base64-headers:**
   - När en klient gör anrop utan `PAYMENT-SIGNATURE`:
     - Returnera **HTTP 402 Payment Required**.
     - Skicka alltid Base64-kodad header `PAYMENT-REQUIRED` med:
       - `x402Version: 2`
       - `network: "eip155:8453"` (Base Mainnet)
       - `asset: "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913"` (Base USDC)
       - Belopp i 6 decimaler: `5000` (0.005 USDC), `20000` (0.02 USDC), `150000` (0.15 USDC).
       - `payTo: "0x4b78631d51a665Aeb924F061b36996f7c87c2B06"`
   - När `PAYMENT-SIGNATURE` skickas:
     - Verifiera payload, spara transaktionshash i SQLite och returnera `PAYMENT-RESPONSE` samt 200 OK med live-data.
2. **Skapa `/api/catalog` (0,00 USDC):**
   - Returnera fullständig JSON-katalog med alla rutter, priser, beskrivningar och metoder.
3. **Prisuppdatering:**
   - Uppdatera endpoints till 0,005 / 0,020 / 0,150 USDC.
4. **Telemetri i `/admin`:**
   - Visa två tydliga mätare: `402 Probes` (när katalogbotar efterfrågar prislapp) och `Genomförda köp`.
5. **Synka manifest:**
   - `/llms.txt`, `/agents.json` och `/.well-known/x402.json`.

---

#### ⚡ PASS 2: Skarp Testbetalning på Base Mainnet (Arbetstid: ~30 min)
1. Kör ett testskript från en testplånbok med ~1 USDC på Base Mainnet mot `https://johngarp.click/api/v1/arb-scanner`.
2. Fånga `PAYMENT-REQUIRED` v2-header, signera payloaden, skicka `PAYMENT-SIGNATURE` och ta emot `200 OK` samt `PAYMENT-RESPONSE`.
3. Verifiera att köpet registreras i `/admin` och att transaktionskvittot finns på BaseScan.

---

#### ⚡ PASS 3: Registrering i de 6 Marknadsplatserna (Arbetstid: ~45 min)
1. **`x402apis.io`:** Lägg in `https://johngarp.click/api/catalog`.
2. **`relai.fi/market`:** Registrera AIM Network på Base.
3. **`402.com.tr` / `api-402.com`:** Skicka in endpoint-katalogen.
4. **`Coinbase Bazaar` (CDP):** Registrera `agent.json`.
5. **`x402scan.com`:** Verifiera listning av plånbok och domän.
6. **`Glama.ai`:** Uppdatera MCP-verktygslistan för `https://johngarp.click/mcp`.
7. **GitHub Repo Topics:** Tagga repo med `x402`, `x402-api`, `mcp-server`, `base-usdc`.

---

## 4. Status Checklist

```markdown
- [x] Konkurrensanalys 1 (Marknad, nisch, differentiering) inläst
- [x] Gemini Deep Research (78k API:er, 2-centsregeln, 79%-fällan) inläst
- [x] Cloudflare Bot Fight Mode: Verifierat AV (OFF)
- [x] Cloudflare AI Crawler & Agent Policies: Verifierat ALLOW
- [x] UptimeRobot 5 min keepalive: Verifierat AKTIVT
- [x] Master-Åtgärdsplan V2.1 genererad och sparad
- [x] Pass 1: Koduppgradering x402 v2, /api/catalog, prissänkning & telemetri (71/71 tester godkända)
- [x] Pass 1: Git push & driftsatt live på https://johngarp.click (Verifierat: 200 OK på /api/catalog, 402 PAYMENT-REQUIRED på /api/v1/arb-scanner)
- [ ] Pass 2: Skarp testbetalning på Base Mainnet (0.005 USDC)
- [ ] Pass 3: Katalogregistrering i x402apis.io, relai.fi, 402.com.tr, Bazaar, x402scan, Glama
```
