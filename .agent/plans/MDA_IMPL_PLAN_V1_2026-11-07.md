# 🏗️ Implementation Plan: MDA
**Version:** V1 | **Datum:** 2026-11-07T12:38:00+01:00 | **Status:** DRAFT
**Arkitekt:** John Garp | 🔒 **IMMUTABLE: ORIGINAL PLAN**

> [!IMPORTANT]
> **Denna V1-plan är oföränderlig.** Alla uppdateringar sker i nya versioner (V2, V3...).
> V1 finns alltid tillgänglig som fallback-referens (Se Global Regel R6).

---

## 📊 Projektöversikt
**Total Progress:** [░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░] 0%
**Milestones:** 5 | **Tasks:** 9

### 💰 Kostnadsammanfattning
- **Estimerad total kostnad:** 0 SEK
- **Antal gratis-alternativ funna:** 5
- **Kräver godkännande:** ✅ NEJ
- **GCP Fallback (Credits):** ❌ Behövs ej

---

## 🛣️ Milestones & Tasks

### 🔴 M1: Grundstruktur, Konfiguration & Persistent Databas
**Prio:** 🔴 CRITICAL | **Status:** NOT_STARTED | **Progress:** [░░░░░░░░░░░░░░░░░░░░] 0%
> Sätta upp FastAPI-projektet, miljövariabler (.env med WALLET_ADDRESS och ADMIN_PIN), samt SQLite-databas för persistent lagring av anropsstatistik, intäkter, spanar-logg och förbrukade transaktions-hashar (Replay-skydd).

> [!TIP]
> **Agentens Challenge/Mönster:**
> Genom att använda SQLite (via inbyggda sqlite3) med WAL-mode istället för en minnes-dict i Python behålls all statistik och skyddet mot återanvända betalningskvitton (tx_hash replay) även vid omstarter.

*Sektions-test Config: Auto-Test ✅ | Auto-Fix ✅*

#### Tasks
- [   ] **T1.1 — Skapa projektstruktur och beroenden** 🔴 *(Kostnad: 0 SEK)*
  - **AC:** requirements.txt innehåller fastapi, uvicorn, httpx, pydantic-settings, pytest, .env.example innehåller WALLET_ADDRESS, ADMIN_PIN, X402_VERIFY_MODE och BASE_RPC_URL
  - 🔸 S1.1.1: Skapa requirements.txt, .gitignore och .env.example (`c:/Users/johnr/Documents/MDA/requirements.txt`) 🔴
  - 🔸 S1.1.2: Skapa konfigurationsmodul (`c:/Users/johnr/Documents/MDA/app/config.py`) 🔴
- [   ] **T1.2 — Implementera SQLite-databas för stats, tx-logg och spanar-förslag** 🔴 *(Kostnad: 0 SEK)*
  - **AC:** Tabeller för system_state, used_transactions och discovery_logs skapas automatiskt, Stöd för att kontrollera om en tx_hash redan har använts (replay protection)
  - 🔸 S1.2.1: Skapa databasmodul (`c:/Users/johnr/Documents/MDA/app/database.py`) 🔴

---

### 🔴 M2: x402 Betalväxel, On-Chain Base RPC-Verifiering & Replay-Skydd
**Prio:** 🔴 CRITICAL | **Status:** NOT_STARTED | **Progress:** [░░░░░░░░░░░░░░░░░░░░] 0%
**Beroenden:** M1
> Bygga HTTP 402 Payment Required middleware/dependency som både kan verifiera riktiga USDC-transaktioner på Base Mainnet via gratis publik RPC och stödja test-kvitton i lokalt testläge.

> [!TIP]
> **Agentens Challenge/Mönster:**
> Kombinerar omedelbar x402-kompatibilitet med riktig on-chain verifiering mot Base Mainnet (https://mainnet.base.org) genom att kontrollera ERC-20 Transfer-loggar för USDC (0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913) till Johns plånboksadress, utan att kosta en krona i RPC-avgifter.

*Sektions-test Config: Auto-Test ✅ | Auto-Fix ✅*

#### Tasks
- [   ] **T2.1 — Bygg x402 Payment Verifier & HTTP 402-svar** 🔴 *(Kostnad: 0 SEK)*
  - **AC:** Anrop utan X-PAYMENT-PROOF ger HTTP 402 med komplett x402 JSON-specifikation (network: base-mainnet, token: USDC, amount, recipient), När systemet är pausat (Nödstopp) returneras HTTP 503 Service Paused, Återanvänd tx_hash nekas med HTTP 402/409 (Replay-skydd), Stödjer både skarp Base RPC-kontroll och simulerad verifiering för enhetstester
  - 🔸 S2.1.1: Skapa x402 betalningsmodul (`c:/Users/johnr/Documents/MDA/app/x402.py`) 🔴

---

### 🔴 M3: Live M2M API-Tjänster (Nivå 1: $0.01 & Nivå 2: $1.00)
**Prio:** 🟡 HIGH | **Status:** NOT_STARTED | **Progress:** [░░░░░░░░░░░░░░░░░░░░] 0%
**Beroenden:** M2
> Implementera de två säljbara API-ändpunkterna med riktig live-data från öppna gratis-API:er (CoinGecko, Fear & Greed Index, DexScreener) med smart caching och fallback.

> [!TIP]
> **Agentens Challenge/Mönster:**
> För att garantera svarstid under 0,5 sekunder (Framgångsfaktor #2 i PDF:en) lägger vi in en in-memory TTL-cache (60 sek) framför de externa API-anropen samt en garanterad fallback om ett externt API tillfälligt svarar långsamt.

*Sektions-test Config: Auto-Test ✅ | Auto-Fix ✅*

#### Tasks
- [   ] **T3.1 — Implementera Nivå 1: /api/v1/crypto-pulse ($0.01 USDC)** 🔴 *(Kostnad: 0 SEK)*
  - **AC:** Kräver 0.01 USDC via x402, Returnerar strukturerad realtids-JSON på under 500 ms (via cache/live-fetch)
  - 🔸 S3.1.1: Skapa datatjänst för live marknadsdata (`c:/Users/johnr/Documents/MDA/app/services/market_data.py`) 🔴
- [   ] **T3.2 — Implementera Nivå 2: /api/v1/deep-market-report ($1.00 USDC)** 🔴 *(Kostnad: 0 SEK)*
  - **AC:** Kräver 1.00 USDC via x402, Levererar djupgående JSON-rapport med actionable_signals och likviditetsanalys
  - 🔸 S3.2.1: Lägg till deep-market-report generator och API-routes (`c:/Users/johnr/Documents/MDA/app/routers/api_v1.py`) 🔴

---

### 🔴 M4: Själv-Marknadsföring (Discovery Manifests) & Autonom Spanar-Modul
**Prio:** 🟡 HIGH | **Status:** NOT_STARTED | **Progress:** [░░░░░░░░░░░░░░░░░░░░] 0%
**Beroenden:** M3
> Skapa maskinläsbara katalogfiler (/llms.txt, /agents.json, /.well-known/ai-plugin.json) samt spanar-modulen (/cron/discover) som identifierar nya efterfrågade M2M-datakällor.

> [!TIP]
> **Agentens Challenge/Mönster:**
> Utöver /llms.txt och /agents.json exponerar vi även /.well-known/agent.json (A2A-standard) och rik OpenAPI-metadata så att alla typer av AI-agenter och MCP-kataloger förstår priser och betalningsinstruktioner direkt.

*Sektions-test Config: Auto-Test ✅ | Auto-Fix ✅*

#### Tasks
- [   ] **T4.1 — Skapa /llms.txt, /agents.json och /.well-known/agent.json** 🔴 *(Kostnad: 0 SEK)*
  - **AC:** GET /llms.txt returnerar tydlig markdown-dokumentation för LLM:er, GET /agents.json returnerar maskinläsbar JSON med x402-betalningskrav och Base-adress
  - 🔸 S4.1.1: Implementera discovery-routes (`c:/Users/johnr/Documents/MDA/app/routers/discovery.py`) 🔴
- [   ] **T4.2 — Implementera Autonom Spanar-modul (/cron/discover)** 🔴 *(Kostnad: 0 SEK)*
  - **AC:** POST/GET /cron/discover genererar och sparar nya konkreta API-förslag i discovery_logs, Visas i Overseer Dashboard under Spanar-logg
  - 🔸 S4.2.1: Skapa spanar-tjänst och route (`c:/Users/johnr/Documents/MDA/app/services/scout.py`) 🔴

---

### 🔴 M5: Overseer Dashboard (/), PIN-skyddat Nödstopp & Produktionspaket
**Prio:** 🟡 HIGH | **Status:** NOT_STARTED | **Progress:** [░░░░░░░░░░░░░░░░░░░░] 0%
**Beroenden:** M4
> Bygga det responsiva Overseer Dashboard-gränssnittet i mörk terminal/command-center-stil med PIN-skyddad Nödstopp-knapp, Spanar-trigger och färdig Render/Docker-konfiguration.

> [!TIP]
> **Agentens Challenge/Mönster:**
> Nödstopp-knappen och manuella admin-triggers säkras med X-Admin-Pin / PIN-prompt i UI:t så att inga utomstående eller botar kan pausa din butik.

*Sektions-test Config: Auto-Test ✅ | Auto-Fix ✅*

#### Tasks
- [   ] **T5.1 — Bygg Overseer Dashboard (/) och Admin-endpoints** 🔴 *(Kostnad: 0 SEK)*
  - **AC:** GET / visar Overseer Dashboard med live-siffror från SQLite, POST /api/admin/toggle-pause kräver giltig ADMIN_PIN och växlar mellan ONLINE och PAUSED
  - 🔸 S5.1.1: Skapa dashboard-vy och admin-API (`c:/Users/johnr/Documents/MDA/app/routers/dashboard.py`) 🔴
- [   ] **T5.2 — Skapa main.py, render.yaml och End-to-End-testsvit** 🔴 *(Kostnad: 0 SEK)*
  - **AC:** render.yaml och Procfile är redo för Render.com Free Tier, Samtliga E2E-tester passerar grönt
  - 🔸 S5.2.1: Skapa app/main.py och render.yaml (`c:/Users/johnr/Documents/MDA/app/main.py`) 🔴

---
