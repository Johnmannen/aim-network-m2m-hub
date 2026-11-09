<!-- cSpell:disable -->
# AIM Network — Katalog- och Marknadsplatsregistrering

Detta dokument beskriver hur AIM Network (`https://johngarp.click`) listas och
exponeras mot autonoma AI-agenter, MCP-klienter och x402-nätverk.

---

## 1. Genomfört Automatiskt av Agenten

1. **GitHub Repository Topics:**
   - Repot `Johnmannen/aim-network-m2m-hub` har taggats via GitHub CLI med:
     `x402`, `x402-api`, `base-usdc`, `mcp-server`, `ai-agents`,
     `autonomous-agents`, `base`, `usdc`, `mcp`, `m2m`, `llms-txt`, `fastapi`.
   - Detta gör att GitHubs och communityns crawler-botar omedelbart indexerar
     repot som en x402-resurs.
2. **Maskinläsbara Kataloger Live på `johngarp.click`:**
   - `GET /api/catalog` (0,00 USDC, fullständig JSON-katalog över alla 14
     endpoints).
   - `GET /.well-known/x402.json` (officiell discovery-card med Base
     USDC-kontrakt och facilitator).
   - `GET /.well-known/agent.json` (A2A Agent Card för
     Google/Coinbase/LangChain).
   - `GET /llms.txt` (Komplett specifikation och systemprompt för LLM:er).
   - `GET /mcp` (Uppdaterad med alla nya verktyg: `get_arb_scanner`,
     `get_sentiment_signals`, `get_multi_source_dossier`).

---

## 2. Åtgärder för John (1-klicksregistreringar)

### A. Smithery.ai (Största registret för Claude Desktop, Cursor & Windsurf)

- **Länk:** [https://smithery.ai/publish](https://smithery.ai/publish)
- **Steg:**
  1. Gå till länken och logga in med ditt GitHub-konto (`Johnmannen`).
  2. Välj repot: `Johnmannen/aim-network-m2m-hub`.
  3. Smithery läser automatiskt in `smithery.yaml` och verifierar
     `https://johngarp.click/mcp`.
  4. Klart! Servern och alla verktyg publiceras publikt i Smithery-katalogen.

### B. Glama.ai (MCP Index)

- **Status:** Redan aktiv och verifierad!
- **Verifikations-claim:** `glama_claim_kMQwR0tBTjmF1CxnpiYj2Cgs6m2DT753`
  serveras live på `https://johngarp.click/.well-known/glama.json`.

### C. PulseMCP och MCP Servers Directory

- **Länk:** [https://pulsemcp.com](https://pulsemcp.com)
- **Steg:**
  - Klicka på "Submit Server" och ange:
    - **Name:** `AIM Network`
    - **URL:** `https://johngarp.click/mcp`
    - **GitHub:** `https://github.com/Johnmannen/aim-network-m2m-hub`

### D. x402 Bazaar och Coinbase CDP Indexering

- **Status:** Automatisk indexering!
- Enligt den officiella x402- och Bazaar-arkitekturen indexeras tjänsten
  automatiskt av noderna när `/.well-known/x402.json` och `/api/catalog`
  exponeras med giltiga x402 v2-headers (vilket nu är aktivt live på
  `johngarp.click`).
- Så fort en första skarp transaktion eller bot-probe träffar Base-kontraktet
  registreras plånboken på `x402scan` och i Bazaars historik.
