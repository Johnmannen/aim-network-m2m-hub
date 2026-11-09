# Granskningsrapport: AIM Network (johngarp.click)

*Granskning ur köparens/kundens perspektiv · 8 november 2026 · MCP: johngarp.click/mcp*

## 1. Sammanfattning

AIM Network är en x402-betalad API-hub på Base L2 med fyra datafeeds, ett MCP-manifest och bra maskinläsbar discovery (llms.txt, agents.json, agent.json). Konceptet är tydligt och prissättningen enkel att förstå. Som köpare hade jag dock stannat före första betalningen av tre skäl:

1. **Den "live" BTC-kursen i gratis-teasern verkar inte vara live.** Den visar exakt 89 450,0 USD, medan marknadspriset veckan före låg runt 76 000–80 000 USD. Samma siffror finns i schema-exemplet, vilket tyder på hårdkodad data eller en fallback.
2. **Betalningsmodellen har hål.** Ett tx-hash är publikt på Base och kan återanvändas av vem som helst. 24h VIP-passet (1 000 anrop för 2 USDC) och "Buy 1, Get 5 Free" går därför att dela eller missbruka, och bonusen ger negativ marginal på Deep Market Report.
3. **MCP-servern ser inte ut som en standardkompatibel MCP-server.** GET /mcp returnerar ett eget JSON-manifest, inte JSON-RPC-handshaken som MCP-klienter förväntar sig.

**Totalbetyg (köparperspektiv):** Idé och discovery 8/10 · Dataförtroende 3/10 · Betalningsflöde 5/10 · MCP-kompatibilitet 4/10 · Trovärdighet/juridik 4/10. Poängen är min bedömning, inte en mätning.

## 2. Vad jag testade och vad jag inte kunde testa

**Testat (publikt, utan betalning):**

- Startsidan, /mcp (GET), /api/v1/free-teaser, /llms.txt, /agents.json, /.well-known/agent.json, /docs (Swagger UI) och /admin (bara inloggningssidan).
- Faktakontroll av BTC-priset mot nyhetskällor.

**Kunde inte testa (viktigt att veta):**

- **De betalda endpointsen.** Mitt verktyg fick bara ett generiskt klientfel på /crypto-pulse och /deep-market-report (troligen 402), utan att jag kunde se statuskod, headers eller body. Därför har jag inte kunnat granska 402-svarets innehåll (`accepts`, `X-PAYMENT-RESPONSE`).
- **?sample=true.** Samma klientfel, så jag kan inte bekräfta att gratis-schemat fungerar, trots att llms.txt lovar det.
- **MCP via POST/JSON-RPC** (initialize, tools/list, tools/call). Mitt verktyg gör bara GET.
- **Riktiga betalningar** (jag har ingen plånbok) och /openapi.json (kunde inte hämtas).

I avsnitt 8 finns kommandon så att du själv kan verifiera de punkter jag inte nådde.

## 3. Det som fungerar bra

- **Utmärkt discovery för agenter.** llms.txt, agents.json, /.well-known/agent.json, MCP-manifest och Swagger finns och är konsekvent länkade.
- **Tydlig prisstege:** 0 / 0,01 / 0,05 / 1,00 USDC, plus ett VIP-pass. Lätt för en agent att räkna på.
- **Gratis teaser utan autentisering** gör att en agent kan verifiera att tjänsten lever.
- **Inga konton eller API-nycklar**, vilket passar M2M.
- **Tool-beskrivningar i MCP innehåller pris och endpoint-URL**, så en agent kan fatta köpbeslut utan att läsa dokumentation.
- **Snabb respons** på de sidor jag hämtade, och korrekt ISO-tidsstämpel i teasern.
- **Admin är noindex** och bakom inloggning.

## 4. Fynd, prioriterade

### 4.1 Kritiskt

**K1. Gratis-teasern visar sannolikt inte live-data**

- Teasern returnerar `btc_spot_preview_usd: 89450.0`, `change_24h_pct: 1.2`, `volume_24h_usd: 45000000000` och sentiment "bullish".
- Exakt samma värden finns i `schema_sample`. Siffrorna är runda och oförändrade, typiskt för mock- eller fallback-data.
- Nyhetsflödet 5–6 november 2026 visar BTC runt 80 000 USD, och därefter under 76 000 USD. Ett pris på \~89 450 skulle vara ungefär 12–18 % fel. Jag har inte kunnat verifiera exakt kurs 8 november, men ett så stort hopp på två dagar är osannolikt.
- Status är ändå `LIVE_FEED_VERIFIED`. Det är det mest skadliga: en agent som litar på statusen handlar på fel data.

*Risk:* felaktig data i en tjänst som säljs som "live" och "actionable trading signals" ger förlorat förtroende, återkrav och möjligt ansvar.

*Lösning:*

- Hitta orsaken: misslyckat upstream-anrop som tyst faller tillbaka på en konstant, cache som aldrig går ut, eller en hårdkodad demo.
- Returnera aldrig en konstant som "live". Vid upstream-fel ska svaret vara 503 eller en tydlig `"status":"DEGRADED"`.
- Lägg till `source`, `as_of` (tidpunkt för källdatan) och `age_ms` i varje svar.
- Kontrollera priset mot minst två oberoende källor och flagga avvikelser över t.ex. 1 %.
- Använd tydligt märkt exempeldata (t.ex. `"example": true`) i `schema_sample`, inte siffror som ser ut som livepriser.

### 4.2 Hög

**H1. Tx-hash-flödet kan återanvändas och delas**

- Ett tx-hash på Base är publikt. Servern kan inte veta *vem* som skickar hashen i `X-PAYMENT-PROOF`.
- VIP-passet (1 000 anrop/24h) kan därför läggas upp offentligt och användas av obegränsat många. Samma sak gäller bonusanropen.
- Det går också att "återanvända" en betalning från någon annan till din adress.

*Lösning:*

- Prioritera standard-x402 (EIP-3009, signerad av betalaren) och gör tx-hash till legacy.
- Om tx-hash behålls: binda beviset till betalarens plånbok genom en signatur över en server-nonce (t.ex. EIP-191/SIWE) och verifiera att signeraren är tx:ens `from`.
- Registrera varje hash i databas med räknare, utgångstid och plånbok.
- Rate limit per plånbok och per IP.
- Kontrollera belopp, token-kontrakt, mottagare, chain id och antal confirmations (reorg-skydd).

**H2. Bonus- och passekonomin ger negativ marginal**

- "Buy 1, Get 5 Free": en första betalning på 0,01 USDC ger 5 gratis anrop över *alla* endpoints i 24h. Fem anrop mot Deep Market Report är värda 5,00 USDC.
- VIP-pass: 2,00 USDC för upp till 1 000 anrop över alla endpoints. Mot Deep Market Report (1,00 USDC) är det upp till 1 000 USD i listpris. Nya plånböcker är gratis att skapa, så "ny plånbok"-regeln är lätt att kringgå.
- Du betalar dessutom upstream-kostnader och rate limits (t.ex. DexScreener).

*Lösning:*

- Begränsa bonusen till billiga endpoints (crypto-pulse) eller till ett fast kreditvärde, t.ex. "bonus = 5 × 0,01 USDC".
- Ändra VIP-passet till en kredit- eller kvotmodell, t.ex. 2 USDC = max 200 anrop mot billiga endpoints, eller dela upp per endpoint. Separat, högre pass för Deep Report.
- Sätt hårda tak per dygn och per endpoint, samt avtal och kostnadsbudget mot upstream.

**H3. Oklart vilka betalningsflöden som gäller**

- Startsidan visar `X-PAYMENT` (signerad EIP-3009). agents.json säger `header_name: X-PAYMENT-PROOF`. llms.txt nämner båda plus en v2-header `PAYMENT-SIGNATURE`.
- Nätverket heter `base-mainnet` i manifesten men `base` i x402-`accepts`.
- En agent som följer agents.json får ett annat flöde än en som följer startsidan.

*Lösning:* ett primärt flöde (standard x402) dokumenterat på ett ställe. Övriga markeras "legacy". Generera alla manifest från samma källa så de inte driver isär.

**H4. Gratis-schema (?sample=true) kunde inte bekräftas**

Det är den viktigaste köpbarriären-sänkaren (testa innan jag betalar). Om den inte fungerar eller kräver betalning bryter det ett uttryckligt löfte i llms.txt och agents.json. Verifiera med kommandona i avsnitt 8.

### 4.3 Medel

**M1. MCP-servern är troligen inte standard-MCP**

- GET /mcp returnerar `{"mcp_version":"2025-03-26","server_name":...,"tools":[...]}`, ett eget format. En standardserver svarar på JSON-RPC 2.0: `initialize` (med `protocolVersion`, `capabilities`, `serverInfo`), sedan `tools/list` och `tools/call`, över Streamable HTTP (eller SSE).
- llms.txt påstår att /mcp även är "JSON-RPC". Jag kunde inte testa POST, så det kan stämma, men manifestet saknar `protocolVersion` och `capabilities`.
- Betalda verktyg har bara en valfri `payment_proof`-parameter. Det saknas dokumenterat sätt att hantera 402 över MCP, så en agent vet inte vad den ska göra när betalning krävs.
- Trending-endpoints finns inte som MCP-verktyg.

*Lösning:*

- Bygg om /mcp med officiell SDK (FastMCP/MCP Python SDK) med Streamable HTTP, och testa med MCP Inspector.
- Lägg `outputSchema` och annotations (`readOnlyHint: true`, `idempotentHint: true`).
- Definiera tydligt betalbeteende: returnera ett verktygsfel med `payment_required` och 402-kraven i strukturerat format, och ta emot bevis via param eller header.
- Lägg till `get_trending_asset(slug)` och `list_trending_assets`.

**M2. Trending-endpoints är inkonsekvent beskrivna och svåra att upptäcka**

- Startsidan nämner Morpho, XRP, WLD. llms.txt och agents.json listar bara `wasted`, och namnet är dubblerat: "WASTED (WASTED)".
- Det finns ingen lista över tillgängliga slugs och inget MCP-verktyg. En agent kan inte veta vilka feeds som finns.
- Att tjänsten "auto-deployar" feeds för momentum-tokens är en risk: lågkvalitativa eller manipulerade tokens (honeypots, wash trading) kan marknadsföras som signaler.

*Lösning:*

- Lägg till `GET /api/v1/trending` (gratis lista med slug, symbol, senast uppdaterad, likviditet).
- Minimikrav för auto-publicering: likviditet, ålder, antal holders, volymkvalitet. Flagga risk (`risk_flags`).
- Validera `{slug}` strikt mot allowlist (inga fria strängar).

**M3. Datakällor och licenser**

- Startsidan säger "Aerodrome & Uniswap", llms.txt säger "via DexScreener", och Fear & Greed-index hämtas troligen från tredje part.
- Kontrollera att villkoren för varje källa tillåter kommersiell återförsäljning och vilka attributionskrav som gäller. Jag har inte läst dem här och är inte jurist.
- Beskriv datakällor och uppdateringsfrekvens öppet, i varje svar och i dokumentationen.

**M4. Marknadsföringspåståenden utan belägg**

- "Institutional", "actionable trading signals", "ultra-fast" och "sub-150ms" saknar metodbeskrivning, mätdata och statussida.
- Ordet "trading signals" kan i EU/Sverige dra till sig regelkrav kring investeringsrådgivning. Jag är inte jurist, men en disclaimer ("informationsdata, ingen investeringsrådgivning") och en juridisk kontroll är rimligt.

*Lösning:* publicera metodik, uppdateringsfrekvens och mätt latens (p50/p95), samt en statussida. Byt ut "institutional" om du inte kan styrka det.

**M5. Saknade villkor, refund-policy och kontakt**

- Jag hittade inga användarvillkor, integritetspolicy, supportkontakt eller information om vem som driver tjänsten.
- On-chain-betalning går inte att ångra. Vad händer om upstream är nere eller svaret är fel efter betalning?

*Lösning:*

- Lägg till /terms, /privacy, /contact och /status.
- Kräv betalning först när svaret är redo att levereras (x402-settle efter lyckat svar), så att 5xx inte debiteras. Gör anropen idempotenta med ett request-id.
- Beskriv eventuell återbetalningsprocess.

### 4.4 Låg

**L1. /admin länkas från publika startsidan.** Sidan är noindex och inloggningsskyddad, men länken visar var den finns. Ta bort den från footern, lägg admin bakom IP-allowlist/VPN och 2FA, och rate limita inloggning. Inloggningssidan är dessutom på svenska medan resten är engelska, vilket avslöjar mindre men är inkonsekvent.

**L2. Publik Swagger (/docs).** Normalt för ett API-produkt, men kontrollera att inga interna eller admin-routes syns i schemat. Dölj dem med `include_in_schema=False`.

**L3. /.well-known/agent.json är identisk med agents.json.** A2A-agentkort förväntar sig ett eget schema (name, url, version, capabilities, skills m.m.). Idag fungerar filen som en kopia. Antingen gör ett riktigt A2A-kort eller ta bort påståendet "A2A Agent Card" i llms.txt.

**L4. Mottagarplånbok.** Plånboksadressen är publik (normalt), men använd en dedikerad mottagaradress, svep intäkter regelbundet till cold storage och övervaka inkommande transaktioner och larma på avvikelser.

**L5. Förtroende i domän och presentation.** `.click` är en TLD som ofta förknippas med spam, och vissa filter blockerar den. Sidan är bara på engelska och saknar exempel på betalda svar. Visa en komplett exempelrespons per endpoint, en changelog och en tydlig ägare/kontakt.

**L6. Saknade standardhuvuden.** Jag kunde inte se response headers, men överväg `Cache-Control`, `ETag`, `X-RateLimit-*` och `Retry-After` så agenter kan cacha och backa korrekt.

## 5. Köpresa: var jag skulle ramla av

| Steg | Upplevelse | Status |
| --- | --- | --- |
| Hitta tjänsten | llms.txt, agents.json, MCP, Swagger | Bra |
| Förstå priset | Tydlig prisstege | Bra |
| Testa gratis | Teaser fungerar men visar trolig fel kurs | Brister |
| Se schema före köp | ?sample=true lovas, kunde inte bekräftas | Oklart |
| Betala | Två/tre olika flöden, motstridig dokumentation | Brister |
| Få data | Ej testat (kräver betalning) | Ej testat |
| Lita på data | Ingen metodik, källa eller as\_of | Brister |
| Få hjälp | Ingen kontakt eller status | Saknas |

## 6. Åtgärdsplan

**Idag (P0)**

1. Utred och åtgärda den hårdkodade/fallback-BTC-kursen. Ta bort `LIVE_FEED_VERIFIED` när data inte är färsk.
2. Pausa eller begränsa VIP-passet och bonusen tills återanvändning av tx-hash är åtgärdad.
3. Verifiera ?sample=true och 402-svaren med curl (avsnitt 8).

**Denna vecka (P1)**

4. Binda betalningsbevis till plånbok, med server-side räknare och utgång. Gör standard-x402 till primärt flöde.
5. Räkna om bonus- och passekonomin (kredit/kvot, tak per endpoint).
6. Bygg om /mcp med officiell SDK och testa med MCP Inspector.
7. Samordna dokumentationen: ett betalflöde, en namngivning av nätverk, genererade manifest.
8. Lägg in `source`, `as_of`, `age_ms` och disclaimer i alla svar.

**Inom en månad (P2)**

9. Terms, privacy, kontakt, status och refund-policy.
10. Trending-index, riskflaggor och MCP-verktyg för trending.
11. Dölj admin från publika sidor, 2FA och IP-allowlist.
12. Verifiera datalicenser, juridisk genomgång av "trading signals".
13. Riktigt A2A-agentkort och Swagger-rensning.

## 7. Föreslagen minimal datastruktur i svar

```json
{
  "data": { "...": "..." },
  "meta": {
    "source": ["coingecko", "dexscreener"],
    "as_of": "2026-11-08T11:37:26Z",
    "age_ms": 820,
    "status": "OK",
    "request_id": "uuid",
    "disclaimer": "Information only. Not investment advice."
  }
}
```

## 8. Verifiera själv: kommandon

```bash
# 402-svaret (statuskod, headers, body)
curl -i https://johngarp.click/api/v1/crypto-pulse

# Gratis-schema
curl -i "https://johngarp.click/api/v1/crypto-pulse?sample=true"
curl -i "https://johngarp.click/api/v1/deep-market-report?sample=true"

# MCP-handshake (ska ge protocolVersion, capabilities, serverInfo)
curl -i -X POST https://johngarp.click/mcp \
  -H 'content-type: application/json' \
  -H 'accept: application/json, text/event-stream' \
  -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-03-26","capabilities":{},"clientInfo":{"name":"test","version":"0"}}}'

# Interaktiv MCP-test
npx @modelcontextprotocol/inspector

# Jämför BTC-kursen med en oberoende källa
curl -s https://johngarp.click/api/v1/free-teaser
```

**Testa även:** återanvänd samma tx-hash från två olika klienter/IP-adresser och se om båda släpps in. Skicka ett för litet belopp, fel token och fel mottagare och se att alla avvisas.

## 9. Slutsats

Fundamentet är bra: tydlig positionering, bra discovery och ett enkelt prisupplägg. Innan du marknadsför tjänsten bör du fixa tre saker: **(1) att "live"-data faktiskt är live, (2) att betalbevis inte kan delas eller återanvändas, och (3) att /mcp pratar standard-MCP.** När de är på plats kan jag gärna göra en ny granskning, och då även av de betalda endpointsen om du ger mig exempelsvar eller kör kommandona ovan och klistrar in resultaten.

## 10. Uppföljning efter åtgärder (8 november 2026)

**Underlag och begränsning:** Bedömningen bygger på råsvar som ägaren klistrade in (free-teaser, crypto-pulse?sample=true, 402-svar, agent.json, MCP tools/list). Mitt eget hämtningsverktyg serverade fortfarande ett cachat svar (samma tidsstämpel som i första granskningen), så jag har inte kunnat verifiera svaren oberoende. Betygen är villkorade av att de inklistrade svaren är äkta.

### Åtgärdat enligt underlaget

- **K1:** BTC visas nu som \~75 880 USD med färsk tidsstämpel, `meta` med källa (Coinbase spot) och `is_schema_example: true` i schema-exemplet. Nivån stämmer med nyhetsflödet 5–6 november.
- **H2 (delvis):** Pass har delats upp i Micro (2 USDC, 1 000 anrop) och Pro (10 USDC, 500 anrop inkl. Deep Report).
- **M1:** MCP svarar med korrekt JSON-RPC 2.0-struktur på `tools/list` och har fått `list_trending_assets`.
- **M3/M4:** disclaimer och `meta` (`sources`, `as_of`, `latency_ms`, `status`) finns i svaren.
- **L3 (delvis):** agent.json är nu ett eget kort med `capabilities` och `skills`.
- 402-svaret har nu en v2-header (`payment-required`, base64) med `eip155:8453`, belopp 10000 (= 0,01 USDC med 6 decimaler) och rätt USDC-kontrakt.
- `Cache-Control: no-store` på alla endpoints.

### Nya eller kvarstående fynd

| # | Prio | Fynd | Förslag |
| --- | --- | --- | --- |
| N1 | Hög | **H1 är inte åtgärdad.** 402-instruktionerna säger fortfarande att man ska skicka transaktionshash i `X-PAYMENT-PROOF`. Ett publikt hash kan delas och återanvändas, så båda passen kan spridas. | Bind beviset till betalarens plånbok (signerad nonce), räknare och utgång per hash, eller gör standard-x402 (EIP-3009) till enda flödet. |
| N2 | Hög | **Gratis-samplet läcker den betalda produkten.** `crypto-pulse?sample=true` returnerar live-värden (BTC, F&G, tidsstämpel) och är i praktiken samma payload som den som kostar 0,01 USDC. | Låt samplet vara tydligt statiskt/fördröjt (t.ex. avrundat, 15 min gammalt) eller returnera bara strukturen. |
| N3 | Hög | **Datakvalitet i samplet:** ETH 2240.0, SOL 89.5, ändringar 0.2/-0.4 och volymer som 14000000000.0/520000000.0 ser ut som rundade platshållare men märks `LIVE_FEED_VERIFIED`. | Verifiera mot källan. Märk fält som inte är live. |
| N4 | Medel | **"bullish" motsäger datan:** `market_sentiment: bullish` samtidigt som Fear & Greed = 28 (Fear) och veckan före var nedåtgående. Samma etikett fanns i den gamla versionen, så logiken verkar statisk. | Härled sentimentet från data (t.ex. F&G + momentum) och dokumentera regeln. |
| N5 | Medel | `volatility_index` bytte skala (42.5 → 0.37) med oförändrad etikett "MODERATE". Skalan är odokumenterad. | Dokumentera enhet och tröskelvärden. |
| N6 | Medel | **Blandning av x402 v1 och v2.** Headern är v2 (`eip155:8453`), men body är v1 (`maxAmountRequired`, `network: base`, `x402Version: 1`) och `x-payment-version: x402/1.0`. Två headernamn (`X-PAYMENT`, `X-PAYMENT-PROOF`) lever kvar. | Välj v2 som primärt, markera v1/tx-hash som legacy, generera alla manifest från samma källa. |
| N7 | Medel | **Dokumentationen motsäger passuppdelningen.** 402-bodyn och llms.txt (som jag såg den) säger fortfarande "1000 calls across ALL endpoints" för 2 USDC. | Uppdatera 402-body, llms.txt, agents.json, startsidan och MCP-beskrivningar. |
| N8 | Medel | **Passekonomi:** Micro = 0,002 USDC/anrop (mot 0,01–0,05 listpris). Pro = 0,02 USDC/anrop vid full användning mot 1,00 USDC listpris för Deep Report, dvs 98 % rabatt. Bara hållbart om marginalkostnaden är nära noll och upstream tål det. | Sätt tak per endpoint/dygn, räkna kostnad per anrop, överväg kreditmodell. |
| N9 | Medel | **Latens:** `latency_ms: 1161.6` i samma svar som lovar "sub-150ms". | Mät p50/p95 och justera löftet eller cachelagra bättre. |
| N10 | Medel | **Agentkortet följer troligen inte A2A-specen.** `$schema`-domänen (a2a-standard.org) kunde jag inte koppla till projektet. `skills` saknar enligt min kännedom `tags`, kortet saknar `defaultInputModes`/`defaultOutputModes`, och `capabilities` används för egna fält (`mcp`, `payment`). Dessutom exponerar tjänsten inget A2A-gränssnitt. Verifiera mot a2a-protocol.org. | Antingen ett riktigt A2A-kort med fungerande endpoint, eller kalla filen "agent catalog" och ta bort A2A-påståendet. |
| N11 | Låg | `top_trending_sectors` ("x402-M2M-Payments" m.fl.) ser statiskt och självpromotande ut. | Härled från data eller ta bort. |
| N12 | Låg | Prisfeeden har en enda källa (Coinbase). Felbeteende vid avbrott är inte visat. | Lägg minst en reservkälla, avvikelsekontroll och 503/`DEGRADED` vid fel. |
| N13 | Medel | **Fortfarande saknas:** villkor, integritetspolicy, kontakt, status-sida, refund-policy; bevis för `tools/call` med `isError` och `initialize`; svar från `/api/v1/trending`; bekräftad borttagen admin-länk. | Se M5, L1 och avsnitt 6. |

### Uppdaterat betyg (villkorat)

| Område | Före | Efter |
| --- | --- | --- |
| Idé och discovery | 8 | 8 |
| Dataförtroende | 3 | 6 |
| Betalningsflöde | 5 | 5,5 |
| MCP-kompatibilitet | 4 | 7 |
| Trovärdighet/juridik | 4 | 5 |
| **Snitt** | **4,8** | **6,3** |

**Utlåtande:** Stor förbättring på de punkter som var mest synliga för en köpare (datat är nu rimligt och märkt, MCP ser standardkompatibelt ut). Tjänsten fungerar som beta, men den bör inte marknadsföras som "institutional" förrän N1–N3 är lösta. Betalningsbeviset (N1) är den största kvarvarande risken eftersom riktiga pengar redan flödar.

### Nästa steg (prioriterat)

1. N1: bind betalbevis till plånbok eller gå över till ren x402/EIP-3009.
2. N2–N4: gör samplet statiskt eller fördröjt, verifiera ETH/SOL, rätta sentimentlogiken.
3. N6–N7: ett betalningsflöde och en konsekvent dokumentation.
4. N8: sätt tak och räkna om passen.
5. N13: terms, privacy, kontakt, status och refund. Skicka `initialize`, `tools/call` (isError-svar) och `/api/v1/trending`, så uppdaterar jag betyget.

## 11. Andra uppföljningen (8 november 2026, ca 12:25 UTC)

**Verifierat av mig mot produktion:** /terms, /privacy, /refund, /status och /api/v1/trending svarar live (färska tidsstämplar, innehållet stämmer med det som ägaren klistrade in). **Endast inklistrat, ej oberoende verifierat:** MCP `initialize` och `tools/call`, `crypto-pulse?sample=true`, free-teaser, 402-body och agent.json (min hämtning serverar fortfarande cachade svar för redan hämtade URL:er).

### Status för N1–N13

| # | Fynd | Status | Kommentar |
| --- | --- | --- | --- |
| N1 | Delbart tx-hash-bevis | **Ej åtgärdat** | `X-PAYMENT-PROOF` med tx-hash är kvar i 402-instruktionerna, MCP-svaret, agent.json och refund-policyn. Privacy nämner "replay attack prevention", men inget visar att beviset är bundet till betalarens plånbok. |
| N2 | Samplet läcker live-data | **Åtgärdat** | Samplet är nu syntetiskt (nollor, 2026-01-01, `SCHEMA_TEMPLATE_PREVIEW`). |
| N3 | Platshållare märkta live | **Delvis** | Samplet är rättat. Men teasern har kvar `change_24h_pct: 0.5`, `volume_24h_usd: 38000000000.0` och `score: 0.37` oförändrade mellan 12:03 och 12:21 medan priset rörde sig, så det är konstanter blandade med ett live-pris. |
| N4 | Sentiment | **Delvis** | Nu "cautious\_rebound", men regeln är odokumenterad och etiketten är fri text i stället för en uppräkning. |
| N5 | Volatilitetsskala | **Delvis** | Samplet anger "LOW (<1.5%)", men teasern visar `MODERATE` med score 0.37, vilket motsäger tröskeln. |
| N6 | x402 v1/v2 | **Delvis** | Body är fortfarande v1 (`x402Version: 1`, `network: base`) medan headern tidigare var v2. Acceptabelt om det dokumenteras som medveten bakåtkompatibilitet. |
| N7 | Motstridig passdokumentation | **Ej åtgärdat** | 402-bodyn säger Micro-pass = **100** anrop, teasern säger **1 000** anrop för samma 2 USDC. |
| N8 | Passekonomi | **Oklart** | Beror på N7. Vid 100 anrop blir Micro 0,02 USDC/anrop, dvs *dyrare* än enkelköp av crypto-pulse (0,01). Vid 1 000 anrop 0,002 USDC/anrop. |
| N9 | Latens | **Ej åtgärdat** | `latency_ms` 815–1 161 ms mot löftet "sub-150ms" i terms och 402-bodyn. |
| N10 | A2A-kort | **Ej åtgärdat** | agent.json är oförändrad jämfört med förra inklistringen (`$schema`-domänen, saknade `tags`, in/ut-lägen, egna fält under `capabilities`). |
| N11 | Statiska sektorer | **Åtgärdat i samplet** | Strängarna finns kvar men sitter nu i en tydlig mall. |
| N12 | Reservkälla/felbeteende | **Oklart** | Teasern listar bara Coinbase + F&G, medan /status listar `binance_stats` som HEALTHY. Var kommer 24h-ändring och volym ifrån? |
| N13 | Villkor, policy, kontakt, status | **Åtgärdat (grund)** | Sidor finns, se nedan. |

**MCP:** `initialize` och `tools/call` med `isError: true` är korrekt byggda. Dock returnerar `initialize` protokollversion 2024-11-05 medan manifest och agent-kort annonserar 2025-03-26 (och transporten skiljer sig mellan versionerna). Felsvaret hänvisar fortfarande till tx-hash-flödet.

### De nya juridiska sidorna (verifierade)

**Bra:**

- Refund-policyn är stark: i standard-x402 settlas betalningen först efter lyckat HTTP 200, och 5xx, timeout eller degraderad feed debiteras aldrig.
- Kontakt (support@johngarp.click) finns, liksom ett maskinläsbart /status.
- Terms har rate limit (60 req/min/IP), disclaimer och datum.

**Brister:**

- **Endast JSON, ingen läsbar sida.** Det räcker inte som villkor för människor och jurister.
- **Operatören är anonym** ("AIM Network"). Inget juridiskt namn, orgnr, land, tillämplig lag eller ansvarsbegränsning.
- **GDPR-lucka:** privacy säger "pii\_collected: None" och listar plånboksadresser, hash, tidsstämplar och svarskoder. Men rate limit per IP förutsätter att IP-adresser behandlas, och IP-adresser (och ofta plånboksadresser) kan vara personuppgifter. Saknas gör personuppgiftsansvarig, rättslig grund och hur man begär utdrag/radering. Jag är inte jurist: låt någon granska.
- **Rate limit per IP** kan drabba legitima agenter bakom delade molnadresser. Begränsa hellre per plånbok.
- **SLA-löftet** ("99.9 % uptime", "<150ms") ligger i terms, men mätvärdena visar 800+ ms. Formulera som mål eller mät p50/p95 offentligt.
- **/status** visar `uptime_24h: 100.0%` med `total_calls_served: 0`.

### Viktigast: 0 betalda anrop

`total_calls_served: 0` betyder att ingen betald transaktion har gått hela vägen genom produktion (verifiering, settlement via facilitatorn, bonus, pass). Kör en riktig testbetalning (0,01 USDC) i **båda** flödena innan tjänsten marknadsförs, och försök återanvända beviset från en annan IP-adress för att bevisa att N1 är stängd.

### Trending

/api/v1/trending fungerar och returnerar 1 tillgång (WASTED). Det motsäger startsidans marknadsföring ("Morpho, XRP, WLD, etc."). Det saknas riskflaggor, likviditet och ålder (M2), och namnet är dubblerat ("WASTED (WASTED)").

### Uppdaterat betyg (andra omgången)

| Område | Före | Efter 1 | Efter 2 |
| --- | --- | --- | --- |
| Idé och discovery | 8 | 8 | 8 |
| Dataförtroende | 3 | 6 | 7 |
| Betalningsflöde | 5 | 5,5 | 6 |
| MCP-kompatibilitet | 4 | 7 | 7,5 |
| Trovärdighet/juridik | 4 | 5 | 6,5 |
| **Snitt** | **4,8** | **6,3** | **7,0** |

**Utlåtande:** Tjänsten är nu en trovärdig beta. Sample-läckan är stängd, MCP fungerar och villkor, refund och status finns. Men N1, N7, N9 och N10 är inte åtgärdade, och ingen betalning har testats i produktion. Jag rekommenderar en mjuk lansering med låga volymer tills de är stängda, och att inte kalla tjänsten "institutional" ännu.

### Nästa steg

1. Kör en riktig betalningstest i båda flödena och försök återanvända beviset från en annan klient.
2. Bind tx-hash-beviset till plånbok eller ta bort flödet. Alternativt gör det strikt legacy med låga tak.
3. Rätta 100 kontra 1 000 anrop i alla dokument (402-body, teaser, llms.txt, startsida, agents.json, MCP).
4. Gör teaserns 24h-fält live eller märk dem som exempel. Dokumentera sentimentets och volatilitetens regler.
5. Gör juridiken läsbar (HTML) med juridiskt namn, lag och GDPR-uppgifter. Låt jurist granska.
6. Rätta agent.json (riktigt A2A eller byt namn) och synka MCP-versionen.

## 12. Tredje uppföljningen (8 november 2026, ca 12:45 UTC, commit 6360670)

**Verifierat av mig:** `/api/v1/trending` svarar live med 3 tillgångar (Morpho, Virtual Protocol, WASTED) och innehållet stämmer med det inklistrade. **Ej verifierat:** free-teaser, agent.json, /terms, /status och övriga svar. För dessa fick jag samma äldre ögonblicksbilder som tidigare (identiska tidsstämplar), så jag kan varken bekräfta eller avfärda ändringarna. Det kan vara cache i min hämtning, men det är värt att kontrollera att inga routes serveras cachade till vissa klienter (`curl -sI` med olika User-Agent, och `cf-cache-status`).

### Status

| Punkt | Status | Kommentar |
| --- | --- | --- |
| N3/N12 live 24h-statistik | **Delvis** | Rätt riktning att räkna från Coinbase /stats. Se D1–D3 nedan. |
| N4 sentiment-enum | **Åtgärdat (enligt underlaget)** | Sex dokumenterade värden. |
| N5 volatilitet | **Delvis** | Score 0.14 stämmer med "LOW (<1.5%)", men se D2. |
| N7/N8 passekonomi | **Åtgärdat (enligt underlaget)** | 500 anrop/2 USDC (0,004/anrop), 50 anrop/10 USDC (0,20/anrop). Hållbart om cachen tar kostnaden; sätt ändå tak per endpoint. |
| M2 trending | **Delvis** | Verifierat live med likviditet, ålder, risk och dex. Se D4. |
| N10 A2A | **Delvis** | Kortet har fått `tags` och per-skill-fält, men följer troligen fortfarande inte A2A-specen. Se D5. |
| Version | **Åtgärdat** | 2024-11-05 överallt (se D6). |
| Juridik/GDPR | **Åtgärdat (enligt underlaget)** | Operatör, lag, rättslig grund och kontakt. Ej verifierat av mig. Se D7. |
| **N1 replay/delbarhet** | **Påstått, ej bevisat** | Det finns ingen testtransaktion eller svarslogg. Se P1–P5. |

### Betalningsintegritet (N1): kvarstående risker

**P1. Pass-bindning bevisar inte vem som anropar.** Att passet "binds till avsändarplånboken (`from`)" visar bara vem som betalade. Hashen är publik, så alla som presenterar den kan använda passet om anroparen inte också bevisar att den kontrollerar `from` (t.ex. signerad nonce). Detsamma gäller front-running: den som ser en ny transaktion kan skicka hashen först och "bränna" den åt sig.

**P2. Gamla transaktioner.** Om servern inte kräver att hashen är *ny* (efter utfärdad betalningsförfrågan, eller inom t.ex. 10 minuter) kan vem som helst skrapa tidigare USDC-överföringar till din mottagaradress från Base och lösa in dem som gratis krediter, inklusive tidigare 10 USDC-belopp som Pro-pass. Kräv också exakt belopp, token, mottagare och chain.

**P3. Persistens.** "Bränns i SQLite" är bara skydd om databasen överlever omstarter. På Render raderas filsystemet vid varje deploy om du inte har en persistent disk. Använd persistent disk eller Postgres, annars nollställs replay-skyddet och passens saldon vid varje driftsättning.

**P4. Bränn efter leverans.** Brännmärk hashen först när svaret levererats (HTTP 200), eller gör anropet idempotent med ett request-id. Annars förlorar köparen betalningen vid fel mellan verifiering och svar, och refund-policyn blir manuell.

**P5. Smarta plånböcker.** Många agent-plånböcker (smart wallets, account abstraction) har ett `from` som är en bundler. Läs USDC `Transfer`-händelsen i kvittot (från, till, belopp) i stället för transaktionens `from`. Kontrollera även finalitet (confirmations) och att transaktionen inte reverterat.

**Så bevisar du N1 (skicka resultatet):**

1. Gör en riktig köp på 0,01 USDC: första anropet ska ge 200, ett andra från annan klient/IP ska ge 402 `REPLAY_REJECTED`.
2. 20 parallella anrop med samma hash: exakt ett får 200.
3. Deploya om, återanvänd hashen: ska fortfarande avvisas.
4. Presentera en gammal USDC-överföring till din adress: ska avvisas.
5. Presentera ett pass-hash utan signatur från en annan plånbok/IP: ska avvisas.
6. Fel belopp (0,009), fel token, fel mottagare, fel chain och reverterad transaktion: ska avvisas.

### Övriga fynd

**D1. Volymen är en enskild börs.** `volume_24h_usd: 148 680 149` kommer från Coinbase Exchange men heter som marknadsvolym (förut 38 miljarder). Döp om till t.ex. `coinbase_volume_24h_usd`. Kontrollera enheten: Coinbase /stats anger volym i basvaluta (BTC), och \~1 960 BTC (148,7 M / 75 885) ser lågt ut för ett dygn. Verifiera omräkningen.

**D2. Volatilitetsmåttet.** Open-till-last över 24h mäter *rörelse*, inte volatilitet. Använd high–low-intervall (finns i /stats) eller realiserad volatilitet och dokumentera formeln.

**D3. "Multi-börs-aggregering".** SLA-texten beskriver live multi-börs-aggregering (300–800 ms), medan `meta.sources` bara visar Coinbase. /status listar dessutom `binance_stats` som HEALTHY fast Binance skulle bytas bort. Uppdatera listan så att källorna stämmer.

**D4. Trending-data ser handlagd ut.** Runda tal (`liquidity_usd` 45 200 000,0 / 28 400 000,0 / 1 250 000,0) och åldrar (180, 120, 45 dagar). Enligt min kännedom lanserades MORPHO och VIRTUAL 2024, så åldrarna stämmer inte om de avser tokens. Jag har inte verifierat mot DexScreener. Hämta likviditet och pooläder från källan, namnge fältet tydligt (`pool_age_days`?), lägg `as_of` per tillgång och dokumentera hur `risk_level` räknas.

**D5. A2A-kortet.** Roten saknar enligt min kännedom `defaultInputModes`/`defaultOutputModes`, `inputModes` ska vara MIME-typer (inte "direct"/"mcp"), `auth` är ett eget fält, och `url` ska vara A2A-gränssnittets endpoint. Dessutom saknas ett A2A-gränssnitt. `$schema`-domänen byttes ut utan källa. Validera mot den officiella specen (a2a-protocol.org), eller byt namn på filen till "agent catalog".

**D6. MCP-transport.** Du annonserar 2024-11-05 (HTTP+SSE) men servern beter sig som Streamable HTTP via POST (2025-03-26). Annonsera den nyare versionen och förhandla ned vid behov.

**D7. Juridik.** (a) JSON-varianten av /terms och /privacy saknar operatör och lag, så den bör följa HTML-versionen. (b) "AIM Network Operations" bör kopplas till en verklig form (enskild firma/AB, organisationsnummer, adress). (c) Exklusivt forum gäller sällan mot konsumenter. (d) Moms och bokföring av USDC-intäkter: rådgör med revisor. Jag är inte jurist.

### Uppdaterat betyg (villkorat)

| Område | Efter 2 | Efter 3 |
| --- | --- | --- |
| Idé och discovery | 8 | 8,5 |
| Dataförtroende | 7 | 7,5 |
| Betalningsflöde | 6 | 6 |
| MCP-kompatibilitet | 7,5 | 7,5 |
| Trovärdighet/juridik | 6,5 | 7 |
| **Snitt** | **7,0** | **7,2** |

**Utlåtande:** Mycket har blivit bättre och mer konsekvent. Det som återstår är *bevisbarhet* i betalningslagret. Betygen höjs inte förrän N1 är demonstrerat med riktiga transaktioner och punkterna P1–P5 är stängda. Tills dess: mjuk lansering med låga belopp, och kalla inte tjänsten "institutional".

## 13. Fjärde uppföljningen (8 november 2026, ca 13:00 UTC, commit f107d01)

**Verifierat av mig:** `/api/v1/trending` svarar live (12:55:48 UTC) och stämmer med det inklistrade, inklusive likviditet, volym, poolålder, riskklass och förklarande `meta`. **Ej verifierat:** allt annat. För /status (12:24:58, med `binance_stats`) och /terms (utan operatör och lag) fick jag samma äldre ögonblicksbilder som tidigare, och free-teaser, agent.json och betalningstesterna har jag inte kunnat se i produktion. Betygen är därför villkorade av att inklistringen är orörd och äkta.

### Status

| Punkt | Status | Kommentar |
| --- | --- | --- |
| P1 passbindning/front-running | **Delvis** | EIP-3009 är rätt väg och löser det. Legacy-hash-flödet är inte löst, se R2. |
| P2 max ålder 15 min | **Delvis** | Stoppar skrapning av gamla transaktioner. Front-running inom fönstret kvarstår. |
| P3 persistens | **Ej godkänt** | Gist-backup är fel lösning, se R1. |
| P4 bränn efter leverans | **Oklart** | Beskrivet för standard-x402. Inte visat för hash-flödet. |
| P5 smarta plånböcker | **Bra design** | Läs `Transfer`-händelsen. Kontrollera även `topics[2]`, kontraktsadress, belopp och finalitet. |
| Testlistan 1–6 | **Beskriven, ej bevisad** | Se R3. |
| D1 volym | **Delvis** | `coinbase_volume_24h_usd` finns nu, men det vilseledande `volume_24h_usd` ligger kvar med samma värde. |
| D2 volatilitet | **Delvis** | Range % ((high−low)/low) är en rimlig metrik, men det är inte Parkinson-estimatorn (som använder ln(H/L)²). Döp om eller använd riktiga formeln. |
| D3 källor | **Delvis** | Binance borttaget (ej verifierat). Terms säger fortfarande "multi-exchange" medan /status säger "Coinbase parallel fetch". `coingecko_spot_fallback` är tillbaka, se R7. |
| D4 trending | **Verifierat bra** | Riktiga DexScreener-mått, definierad poolålder och riskstandard. Se R4–R5. |
| D5 A2A | **Delvis** | Bättre (in/ut-lägen, tags), men se R8. |
| D6 MCP-version | **OK (ej verifierat)** | Annonsera 2025-03-26 och förhandla ned är rätt. |
| D7 juridik | **Delvis** | F-skatt, lag och forum finns. Se R6. |

### Nya och kvarstående fynd

**R1. Gist som databasbackup (hög).** Att spegla databasen (plånboksadresser, hashar, passstatus) till en Gist vid varje transaktion är riskabelt: ett "hemligt" Gist är åtkomligt för alla som har länken, krypteringsnyckel och GitHub-token måste förvaras på servern, GitHubs rate limits kan blockera betalda anrop, och en återställning från en äldre backup kan öppna ett replay-fönster. Personuppgifter lämnar dessutom din kontroll till en tredje part som privacy-sidan inte nämner. Använd Render Persistent Disk eller hanterad Postgres.

**R2. Front-running i legacy-flödet (hög).** Vem som helst kan lyssna på `Transfer`-händelser till din adress och presentera hashen först, inom de 15 minuterna. Köparen får då "replay rejected" och angriparen får datan, eller ett helt VIP-pass. Att binda till händelsens avsändare bevisar vem som betalade, inte vem som anropar. Åtgärd: kräv en signatur (EIP-191, eller ERC-1271 för smarta plånböcker) från `from` över hash + serverns nonce + resurs, eller sälj passen bara via EIP-3009 och returnera en hemlig pass-token vid första inlösen.

**R3. Testbevisen stämmer inte med /status (hög).** Det inklistrade /status-svaret (12:54:10) visar `total_calls_served: 0` och `calls_micro: 0` trots att test 1 och 3 rapporterar HTTP 200. Det kan bero på att testerna kördes i en annan miljö eller med mockad kedja, eller att räknaren inte räknar dem. Men då är det inte produktionstester. Tidsstämpeln `12:54:10.000000` har dessutom exakt noll mikrosekunder, till skillnad från övriga, vilket ser handskrivet ut. Klistra in orörda råsvar: `curl -si`-utdata med `Date`-header, testtransaktionernas hashar som BaseScan-länkar (jag kan hämta länkar du skriver i ett meddelande), och en redeploy följd av en replay.

**R4. `as_of` i trending är anropets tid (medel).** Likviditet och volym var identiska på åtta siffror i mitt anrop 12:55:48 och ditt 12:54:16, men `as_of` visar anropstid. Det vilseleder. Ange `data_as_of` (när DexScreener hämtades) och `age_s`.

**R5. Riskmodellen (medel).** `LOW_SLIPPAGE` baseras bara på likviditet och volym och Morphos likviditet (521 266 USD) ligger knappt över gränsen 500 000. Namnet säger inget om kontraktsrisk, holder-koncentration eller honeypot. Byt namn till `liquidity_class` eller bredda modellen. "Trending" saknar dessutom ett momentum-mått (pris- eller volymförändring).

**R6. Moms och "reverse charge" (medel).** Anonyma plånboksköpare går inte att fastställa som momsregistrerade företag. Därför är påståendet i villkoren osäkert. Köpare i Sverige och konsumenter i EU ger andra regler. Ta bort texten ur villkoren och låt revisor/Skatteverket avgöra moms och bokföring. Publicera momsnummer i stället för att antyda personnummer. Jag är inte jurist eller skatterådgivare.

**R7. CoinGecko-fallback (medel).** Den ursprungliga felaktiga kursen (89 450) kom från en fallback när CoinGecko rate-limitades. Se till att fallbacksvar alltid märks `source` och `status: DEGRADED`, att de avvisas om de avviker mer än t.ex. 1 % från primärkällan, och att inga konstanter kan returneras.

**R8. A2A-kortet (låg).** Nya `$schema`-adressen går inte att verifiera. `auth` och `capabilities.mcp/payment` är egna fält, `url` pekar på startsidan och inget A2A-gränssnitt finns. Validera med officiell SDK (a2a-sdk) eller byt namn på filen till katalog.

### Uppdaterat betyg (villkorat)

| Område | Efter 3 | Efter 4 |
| --- | --- | --- |
| Idé och discovery | 8,5 | 8,5 |
| Dataförtroende | 7,5 | 8 |
| Betalningsflöde | 6 | 6 |
| MCP-kompatibilitet | 7,5 | 7,5 |
| Trovärdighet/juridik | 7 | 7 |
| **Snitt** | **7,2** | **7,4** |

**Utlåtande:** Datalagret har blivit tydligt bättre och trending är verifierat. Betalningslagret är fortfarande det som hindrar högre betyg: designen är rätt i delar (Transfer-händelse, atomär insert, åldersgräns), men front-running, Gist-backup och motstridiga testbevis återstår. Betalningsflöde höjs först när R1–R3 är stängda.

### Nästa steg

1. R1: byt Gist mot persistent disk eller Postgres.
2. R2: signaturkrav för hash-flödet, eller ta bort det och sälj passen via EIP-3009.
3. R3: skicka orörda råsvar och BaseScan-länkar för testtransaktionerna.
4. R4–R5: `data_as_of`, `liquidity_class` och momentum-mått.
5. R6: ta bort momspåståendet och tala med revisor.
6. R7–R8: märk fallbacks, avvisa avvikelser och validera agentkortet.

## 14. Femte uppföljningen (8 november 2026, commit 00a27b6)

**Underlag och metod.** Denna rond bygger på källkoden, inte på inklistrade svar. Jag har läst `app/x402.py`, `app/x402_standard.py`, `app/main.py`, `app/database.py`, `app/services/market_data.py`, `app/routers/api_v1.py` och `app/routers/discovery.py` på commit `00a27b6`, diffat `f107d01..00a27b6`, kört hela testsviten (**45 passed**) samt gjort statisk analys av betalvägen. De produktionssvar ägaren klistrat in (13:07 UTC) stämmer tecken för tecken med literalerna i källkoden. Det gör dem användbara som bevis — och det är så T2 kan fastställas utan eget anrop. Att svaren innehåller `storage_engine`, `liquidity_class` och `momentum_24h_pct` (alla nya i audit-v4) visar att produktionen kör minst denna commit.

### Status R1–R8

| # | Krav | Status | Grund |
| --- | --- | --- | --- |
| R1 | Gist bort från transaktions- och replay-vägen | **Kvarstår (värre)** | `x402.py:363` anropar ett oimporterat `push_to_cloud_gist` i produktionsgrenen → NameError efter settlement. Gist-backupen körs dessutom fortfarande via GitHub Actions. |
| R2 | Front-running löst, EIP-3009 primärt, atomär bränning, 15 min | **Delvis** | EIP-3009 är korrekt byggd, men legacy-hash annonseras fortfarande som primär header och VIP-passet är inte bundet till anroparen. 15-minutersgränsen är otestad. |
| R3 | Förklara /status-0:an och leverera orörda live-bevis | **Kvarstår** | `total_calls_served` är strukturellt alltid 0; inga tx-hashar, BaseScan-länkar eller redeploy-replay finns. |
| R4/R5 | `liquidity_class`, `momentum_24h_pct`, `data_as_of`, `data_age_seconds` | **Delvis (nominellt)** | Fälten finns, men värdena är konstanter och `data_as_of` är anropstiden. |
| R6 | Ren B2B-policy, F-skatt, ingen reverse-charge | **Helt löst** | Ingen reverse-charge-text kvar; B2B-moms, F-skatt, svensk lag, Stockholms tingsrätt och ansvarsbegränsning finns. |
| R7 | Korrekt Parkinson + Coinbase-volymmärkning | **Delvis** | Formeln är exakt rätt; fallback-vägen märker CoinGecko som Coinbase och "LIVE_FEED_VERIFIED". |
| R8 | MCP `initialize` 2025-03-26 + A2A in/ut-lägen | **Delvis** | In/ut-lägen finns i agentkortet, men `initialize` ekar klientens egen version. |

### Nya fynd (T = rond 5)

**T1. Produktionskrasch i standard-x402 (kritisk).** `app/x402.py:363` kör `asyncio.create_task(push_to_cloud_gist(...))`. Funktionen importeras aldrig i modulen och binds ingenstans (`'push_to_cloud_gist' in vars(app.x402)` → False). Körordningen är `verify_and_settle` (329) → `record_paid_call` (341) → NameError (363) → route-handlern returnerar aldrig data. Eftersom `render.yaml` sätter `TESTING=false` gäller detta i produktion: kunden betalar, transaktionen bokförs, och svaret blir HTTP 500 utan `X-PAYMENT-RESPONSE`. Refund-policyns två löften — "5xx debiteras aldrig" och "settlas först efter HTTP 200" — är därmed båda felaktiga; settlement sker före payload-genereringen. Att sviten är grön beror på att `tests/conftest.py` sätter `TESTING=true` globalt och inget test kör standardflödet med `TESTING=false`. Legacy tx-hash-flödet träffar inte raden och fungerar därför — bara det osäkra flödet fungerar.

**T2. Trending-indexet är hårdkodat och märkt som verifierat (kritisk/hög).** `api_v1.py:118–195` innehåller literalerna `521266.08`, `178158.79`, `-1.38`, `245`, `124850.20`, `48900.50`, `2.45`, `42`. Inget DexScreener-anrop görs i `list_trending_tokens`; repoets enda DexScreener-anrop ligger i base-dex-radar. `data_as_of` sätts till `now_iso` (anropstid) och `data_age_seconds: 60` är en konstant, medan `meta.source` påstår `dexscreener_base_l2_verified`. Diffen `f107d01..00a27b6` visar att rundan endast döpte om `risk_level`→`liquidity_class` och `as_of`→`data_as_of` samt la till konstanter. I det inklistrade livesvaret är `timestamp` och `data_as_of` identiska på mikrosekunden, vilket bevisar att fältet är anropstiden.

**T3. `/status` mäter ingenting (hög).** `discovery.py:901` gör `stats.get("total_calls", 0)`, men `get_stats()` returnerar aldrig `total_calls`; fältet är alltid 0, även med trafik. Förklaringen i avsnitt 3 (pytest mot tempdatabas) är alltså inte rotorsaken. De verkliga räknarna `calls_micro`/`calls_premium` är korrekta och båda 0 i 13:07-svaret — ingen betald call har bokförts i produktion. `uptime_24h: "100.0%"` och alla fem `upstreams: HEALTHY` är hårdkodade, inklusive `dexscreener` (som endpointen aldrig anropar) och `payai_facilitator` (konfigurationsberoende).

**T4. Persistensen är inte verifierad och påståendet är felaktigt (hög).** `render.yaml` har `plan: free` och ingen `disk:`-sektion. Dockerfile lagrar i `/app/data`, `DATABASE_PATH` defaultar dit, men `/status` påstår "Render Persistent Disk /data". Inget i repot stöder det; på Free-planen är filsystemet efemärt, så replay-skydd, pass och räknare nollställs vid deploy. P3 kvarstår.

**T5. Legacy-hash och pass är fortfarande primärt och delbart (hög).** `X-PAYMENT-PROOF` annonseras i `llms.txt`, `agents.json`, agentkortet och MCP:s betalverktyg. `check_and_use_vip_pass` (database.py:440) slår upp passet på enbart tx_hash — ingen signatur, nonce eller caller-bindning. Den som ser en `Transfer`-händelse kan presentera hashen först. Refund-policyns "cryptographically tied to the verified on-chain sender address (from)" är missvisande: `from` identifierar betalaren, inte anroparen. 15-minutersgränsen är implementerad men otestad (`MAX_TX_AGE`/`EXPIRED_TRANSACTION` förekommer inte i något test) och hoppas över när `TESTING` är satt.

**T6. Pro-passens kvot verkställs inte (medel).** `create_vip_pass` (database.py:527) använder alltid `VIP_PASS_MAX_CALLS` (500). `PRO_PASS_MAX_CALLS` (50) används bara i texter. En 10 USDC-betalning ger 500 anrop inklusive 1,00 USDC-rapporter — upp till 500 USDC listpris. Både Micro- och Pro-pass skapas dessutom med `tier="premium"`, så Micro-köp räknas som premium i statistiken.

**T7. Fallback märks som live och fel källa (medel).** CoinGecko-grenen i `market_data.py` sätter `feed_status = "LIVE_FEED_VERIFIED"` i stället för `DEGRADED`, och dess globala `usd_24h_vol` kan via `.get(...)` hamna i `coinbase_volume_24h_usd`. Parkinson saknas i fallbacken → 0.0 → klassas "LOW (<1.5%)" som om den var mätt. Teasern har hårdkodade reservvärden (`148680149.0`, `1960.2`).

**T8. MCP-versionen ekas, A2A saknas (låg).** `discovery.py:510–519` returnerar klientens egen `protocolVersion`, så svaret `2025-03-26` bevisar ingenting — `2024-11-05` in ger `2024-11-05` ut. Agentkortet har nu `defaultInputModes`/`defaultOutputModes`, men `url` är startsidan, `auth`/`capabilities.mcp`/`payment` är egna fält och något A2A-gränssnitt finns inte.

**T9. Gist-jobbet skickar IP-adresser till GitHub (medel).** `.github/workflows/autopilot-keepalive.yml:44–57` hämtar `/api/admin/backup-snapshot` var 10:e minut och PATCHar en Gist. Snapshoten (`database.py:export_db_snapshot`) maskar plånboksadresser men exporterar upp till 1 000 `traffic_logs`-rader med rå `client_ip`. Privacy-sidan säger att IP:er lagras "in ephemeral rolling memory logs" och gallras efter 30 dagar — Gist-kopian motsäger det.

### Det som faktiskt är bra

- Parkinson-estimatorn är matematiskt korrekt och dokumenteras i payloaden; trösklar och etiketter hänger ihop.
- `coinbase_volume_24h_usd` och `coinbase_volume_24h_btc` är rätt döpta och generiska `volume_24h_usd` är borta ur crypto-pulse-assets.
- Den lokala `precheck` i x402-standard är omsorgsfull (mottagare, belopp, giltighetsfönster, nonce-format) och facilitatorfel ger fail-closed utan debitering.
- Villkoren är nu rena och juridiskt sammanhängande (B2B, F-skatt, svensk lag, tingsrätt, ansvarsbegränsning); ingen reverse-charge-text finns kvar.
- Refund-sidans princip om att aldrig debitera degraderade feeds är rätt — den behöver bara bli sann i koden (T1).

### Uppdaterat betyg

| Område | Efter 3 | Efter 4 | Efter 5 |
| --- | --- | --- | --- |
| Idé och discovery | 8,5 | 8,5 | 8,5 |
| Dataförtroende | 7,5 | 8 | 6,5 |
| Betalningsflöde | 6 | 6 | 5,5 |
| MCP-kompatibilitet | 7,5 | 7,5 | 7,5 |
| Trovärdighet/juridik | 7 | 7 | 6,5 |
| **Snitt** | **7,2** | **7,4** | **6,9** |

Sänkningen beror inte på att produkten försämrats i intention, utan på att denna rond granskade koden i stället för de inklistrade svaren. Två punkter som höjde betyget i rond 4 visar sig vara fältbyten ovanpå konstanter, och audit-v4 introducerade ett pengaförlustfel i den rekommenderade betalvägen.

### Utlåtande

Plattformen är **inte verifierad och produktionsredo för betalande autonoma M2M-agenter**. Gratis- och discovery-lagret är det; betalningslagret är det inte. Den standardkompatibla x402-vägen ger 500 efter settlement på den deployade commiten, och det enda flöde som fungerar är legacy tx-hash, vars delbarhet inte är åtgärdad. Därutöver är två centrala förtroendeytor — trending-data och /status — inte mätningar utan konstanter.

### Nästa steg (prioriterat)

1. **T1:** ta bort rad 363 i `x402.py`; ta bort `cloud_backup.py`, dess config-nycklar, `render.yaml`-variablerna och Gist-steget i workflowen. Lägg ett test som kör standardflödet med `TESTING=false` och mockad facilitator. Flytta settlement efter payload-generering, eller skriv om refund-löftet.
2. **T3:** `total_calls_served = calls_micro + calls_premium`; beräkna uptime ur `traffic_logs`/starttid; sätt upstream-status ur faktiska probes eller `UNKNOWN`.
3. **T4:** koppla persistent disk med `DATABASE_PATH=/data/aim_network.db` (eller Postgres) och visa en redeploy följd av ett replay-försök.
4. **T2:** hämta pair-data från DexScreener, lagra `fetched_at`, beräkna `data_age_seconds` och `momentum_24h_pct`; eller märk seed-data `is_synthetic: true` / `source: catalog_seed` och ta bort "verified".
5. **T5:** sälj pass enbart via EIP-3009, eller kräv EIP-191/ERC-1271-signatur från `from` över hash + servernonce + resurs. Lägg testerna som prövar gammal tx, front-run och annan klient.
6. **T6–T9:** parametrisera passkvoten per tier, märk fallback `DEGRADED` med rätt källfält, returnera en fast supported MCP-version, och sluta exportera råa IP-adresser.

## 15. Sjätte uppföljningen (8 november 2026, commit ab3acbf)

**Underlag och metod.** Jag har läst diffen `ab3acbf~1..ab3acbf` i sin helhet, kört hela testsviten (**46 passed**, ett nytt test), gjort egna anrop mot DexScreener från denna maskin samt hämtat `/status` och `/api/v1/trending` direkt från produktionen (13:52–13:53 UTC). Det är första gången produktionsbeteendet verifieras direkt i stället för via inklistrade svar.

### Status T1–T9

| # | Fynd | Status | Grund |
| --- | --- | --- | --- |
| T1 | Produktionskrasch i standard-x402 | **Helt löst (krasch)** | Gist-anropet är borttaget ur betalvägen och det nya testet kör exakt produktionsgrenen (`TESTING=false`). Kvarglömt dellöfte: settlement sker fortfarande före payload-generering, se U1. |
| T2 | Trending hårdkodat och märkt som verifierat | **Delvis löst** | Verklig DexScreener-hämtning finns och fungerar (verifierat: MORPHO 1 501 386,82 USD), men produktionen serverar fallback-konstanter med `data_age_seconds: 0`. Dynamiska scout-poster är fortfarande hårdkodade. Se U2–U3. |
| T3 | `/status` mäter ingenting | **Delvis löst** | `total_calls` beräknas nu korrekt och syns i produktion. Men `uptime_24h` och alla fem upstream-statusar är fortfarande hårdkodade. Se U4. |
| T4 | Persistensen inte verifierad | **Kvarstår** | `render.yaml` är oförändrad: `plan: free`, ingen `disk:`-sektion, medan `/status` fortfarande påstår "Render Persistent Disk /data". |
| T5 | Legacy-hash/pass delbart och front-runningsbart | **Kvarstår** | `x402.py` ändrades bara med borttagna Gist-rader. Passet slås fortfarande upp på enbart tx_hash, utan signatur eller caller-bindning. 15-minutersgränsen är fortfarande otestad. |
| T6 | Pro-passens kvot verkställs inte | **Helt löst (otestat)** | `create_vip_pass` väljer nu 50 anrop för Pro (≥10 USDC) och 500 för Micro, och bokför rätt tier. Saknar test. |
| T7 | Fallback märks som live och fel källa | **Delvis löst** | CoinGecko märks nu `DEGRADED` och dess volym blandas inte längre in i `coinbase_volume_24h_usd`. Kvar: teaserns hårdkodade reservvärden (U5). |
| T8 | MCP-versionen ekas, A2A saknas | **Delvis löst** | `initialize` returnerar nu fast `2025-03-26`. Agentkortet saknar fortfarande ett A2A-gränssnitt och `url` pekar på startsidan. |
| T9 | Gist-jobbet skickar IP-adresser | **Delvis löst** | CI-steget och snapshot-exporten är borttagna, så inga IP-adresser lämnar tjänsten automatiskt. Kvar: `cloud_backup.py`, `BACKUP_GIST_ID`/`GITHUB_BACKUP_TOKEN` och `/api/admin/backup-snapshot` som fortfarande returnerar rå `client_ip`. |

### Verifierat åtgärdat

- **T1:** `app/x402.py` har inte längre något anrop till `push_to_cloud_gist`; `asyncio`-importen är nu oanvänd, vilket bekräftar att raden var enda användaren. Det nya testet `test_standard_x402_production_mode_does_not_crash_on_undefined_names` sätter `TESTING=false`, skickar en giltig `X-PAYMENT`, assertar HTTP 200, `x-payment-response` samt att `calls_micro` och `total_calls` blir 1. Det är precis rätt regressionstest: det hade fångat den ursprungliga kraschen.
- **T3 (räknaren):** `get_stats()` returnerar nu `total_calls = calls_micro + calls_premium`. Produktionen visar fältet, och eftersom `calls_micro`/`calls_premium` är 0 är värdet 0 korrekt — inte längre en strukturell bugg.
- **T6:** kvotfördelningen sker på belopp (≥10 USDC → Pro, 50 anrop, tier `pro`), så Micro-köp räknas inte längre som premium.
- **T8:** protokollversionen är fast och kan inte längre styras av klienten.
- **T7 (fallback):** `coingecko_stats_fallback` + `DEGRADED` är korrekt märkt, och `coinbase_volume_24h_usd` faller inte längre tillbaka på CoinGeckos globala volym.
- **T9 (kärnan):** ingen automatisk export av trafikloggar sker längre.

### Kvarstående fynd efter rond 6 (U)

**U1. Settlement sker fortfarande före leverans (medel).** `verify_and_settle` (rad 329) och `record_paid_call` (rad 341) körs innan routen genererar payloaden. Refund-policyn säger att betalningen "settlas on-chain strictly AFTER the application successfully generates and delivers a valid HTTP 200 payload". Så är det inte: om `fetch_crypto_pulse_data()` eller en upstream fallerar efter settlement är kunden redan debiterad. Antingen flyttas settlement efter payload-generering, eller så skrivs policyn om till "settle före leverans, återbetalning via support".

**U2. Produktionens trending serverar fallback-konstanter som färsk data (hög).** Vid 13:53:27 UTC svarade `https://johngarp.click/api/v1/trending?v=14_live` med `meta.source: dexscreener_cached_fallback`, `data_as_of` = anropstiden och `data_age_seconds: 0`, med MORPHO `521828.24 / 172231.95 / -1.27` och VIRTUAL `912214.33 / 1058771.35 / -1.33`. Dessa värden är identiska med de hårdkodade `fallback`-blocken i `market_data.py`. Samma funktion körd från min maskin gav `source: dexscreener_base_live` med MORPHO `1 501 386,82 / 294 746,27 / -1,51`. Slutsats: den live-väg som byggdes fungerar, men i produktion fallerar DexScreener-anropet och endpointen serverar statiska konstanter — med `data_age_seconds: 0` som påstår att de är färska. Etiketten "cached" är också missvisande; inget cachas, värdena är literaler. De siffror som i avsnitt 2 presenterades som "DexScreener levererar live-siffror" (≈521k / ≈172k / −1,27 %) är alltså fallback-konstanterna, inte live-data.

**U3. Dynamiska scout-poster är fortfarande påhittade (hög).** `api_v1.py:150–156` sätter `liquidity_usd: 124850.20`, `volume_24h_usd: 48900.50`, `momentum_24h_pct: 2.45` och `pool_age_days: 42` för varje auto-deployad slug. Produktionens WASTED-post visar exakt dessa tal, nu med samma `data_as_of`/`data_age_seconds` som DexScreener-paketet. Det innebär att en agent som betalar 0,05 USDC för `/api/v1/trending/wasted` ser en falsk likviditetsbild i den kostnadsfria indexlistan.

**U4. `/status` motsäger sig själv (medel).** Vid 13:53:26 UTC rapporterade `/status` `dexscreener: HEALTHY` samtidigt som `/api/v1/trending` en sekund senare föll tillbaka till `dexscreener_cached_fallback`. `uptime_24h: 100.0%` och samtliga fem upstream-statusar är fortfarande hårdkodade strängar, inte mätningar. Det gör statussidan olämplig som driftbevis och som SLA-underlag.

**U5. Teaser har kvar hårdkodade volymreserver (låg).** `api_v1.py:60–61` defaultar `coinbase_volume_24h_usd` till `148680149.0` och `coinbase_volume_24h_btc` till `1960.2` när fältet saknas — vilket är precis vad som händer i CoinGecko-fallbacken. Dessutom klassas volatiliteten som "LOW (<1.5%)" när Parkinson-värdet är 0,0 på grund av saknad H/L-data, i stället för att utelämnas.

**U6. `pool_age_days` beräknas inte för valt par (låg).** Koden väljer paret med högst likviditet, men just de Aerodrome-paren saknar `pairCreatedAt` i DexScreener-svaret, så åldern faller tillbaka på konstanterna 245/140. Fältet ser beräknat ut men är i praktiken hårdkodat för de valda paren.

### Svar på frågorna

**Är den standardkompatibla x402-betalvägen fullt verifierad och stabil?** Kraschbuggen är stängd och regressionsskyddad med ett test som kör rätt gren, så vägen är nu **stabil på kodnivå**. Den är däremot **inte verifierad i produktion**: `/status` visar 0 betalda anrop och 0 i båda tier-räknarna även efter deploy, det finns ingen riktig settlement-transaktion, ingen BaseScan-länk och ingen replay-demonstration. U1 innebär dessutom att refund-löftet fortfarande är osant. Slutsats: stabil, men oprövad med riktiga pengar.

**Kan hubben betraktas som produktionsklar för autonoma agenter?** **Inte ännu.** Gratis- och discovery-lagret är produktionsdugligt och T1-fixen var nödvändig och korrekt. Men tre blockier kvarstår: produktionen serverar statiska konstanter märkta som färska (U2–U3), persistensen är fortfarande efemär och statuspåståendet om persistent disk är felaktigt (T4/U4), och betalbeviset är fortfarande delbart via legacy-hash (T5). Lägg därtill att ingen betalning någonsin bokförts i produktion.

### Uppdaterat betyg

| Område | Efter 4 | Efter 5 | Efter 6 |
| --- | --- | --- | --- |
| Idé och discovery | 8,5 | 8,5 | 8,5 |
| Dataförtroende | 8 | 6,5 | 7,0 |
| Betalningsflöde | 6 | 5,5 | 6,0 |
| MCP-kompatibilitet | 7,5 | 7,5 | 7,5 |
| Trovärdighet/juridik | 7 | 6,5 | 6,5 |
| **Snitt** | **7,4** | **6,9** | **7,1** |

Dataförtroendet stiger 0,5 eftersom fallback-märkningen och volymsepareringen nu är korrekt, men stannar på 7,0 eftersom produktionens trending ändå är konstanter med färskhetsanspråk. Betalningsflödet återgår till 6,0 när P0-kraschen är stängd och kvoterna är rättade, men T5 håller det kvar under 7. Trovärdigheten står stilla: PII-exporten är borta, men statussidan är fortfarande inte sanningsenlig.

### Utlåtande

Rond 6 är den första ronden där en påstådd åtgärd har hållit hela vägen: **T1 är verkligt löst**, med rätt test på rätt gren. Det är ett stort steg och det mest kritiska felet är borta. Övriga punkter är delvis genomförda: koden innehåller nu rätt logik för trending, telemetri, kvoter och protokollversion, men tre av dem fallerar i produktion eller mäter fel saker. Plattformen är en bra beta med ett fungerande gratislager och en nu stabil betalväg — men den är inte produktionsklar för betalande agenter förrän U2/U3, T4 och T5 är stängda och en riktig betalning har demonstrerats.

### Rekommendationer: lansering och katalogregistrering

**Före lansering (P0)**

1. **U2:** hitta varför DexScreener fallerar från Render (logga statuskod och fel), förläng timeout, lägg retry med backoff och hämta båda tokenparen i ett anrop (`/latest/dex/tokens/{a},{b}`). Om fallback ändå används: sätt `data_age_seconds: null`, `is_stale: true` och `source: static_fallback` per tillgång — aldrig `0`.
2. **U3:** hämta likviditet, volym och momentum även för scout-slugs, eller märk dem `is_synthetic: true` och ta bort dem ur den betalbara listan tills de har en källa.
3. **T4:** koppla persistent disk (kräver betald plan) eller flytta till Postgres, sätt `DATABASE_PATH=/data/aim_network.db`, och visa en redeploy följd av ett avvisat replay-försök. Rätta samtidigt `storage_engine`-strängen i `/status`.
4. **T5:** sälj pass enbart via EIP-3009, eller kräv EIP-191/ERC-1271-signatur från `from` över hash + servernonce + resurs. Lägg testerna för gammal tx, front-run och annan klient.
5. **U1:** flytta settlement efter payload-generering, eller skriv om refund-policyn så den stämmer med koden.

**Före katalogregistrering (P1)**

6. **U4:** härled `uptime_24h` och upstream-status ur faktiska probes eller sätt `UNKNOWN`. En katalog som Smithery eller Glama kan mycket väl läsa `/status`; en självmotsägande statussida är sämre än ingen.
7. **T8:** publicera en A2A-endpoint eller döp `/.well-known/agent.json` till agentkatalog och ta bort A2A-påståendet. `url` ska peka på gränssnittet, inte på startsidan.
8. **T9:** radera `cloud_backup.py`, config-nycklarna och `render.yaml`-variablerna, eller maska `client_ip` i `/api/admin/backup-snapshot`. Döda kod med PII-export är en onödig attackyta.
9. **Bevisa betalningen:** kör en riktig 0,01 USDC-betalning via `X-PAYMENT`, visa BaseScan-länken, försök sedan återanvända beviset från en annan IP och visa att det avvisas. Publicera `total_calls_served: 1` som kvitto. Först då finns det underlag för betyget 8+.
10. **Kataloger:** registrera i Smithery, Glama och PayAI först efter punkt 1–9. Se till att `tools/list`-beskrivningarna matchar faktiskt beteende, att priserna i MCP/manifest/402 är identiska och att `agents.json` inte annonserar `X-PAYMENT-PROOF` som primär header när EIP-3009 är den rekommenderade vägen.

## 16. Sjunde uppföljningen (8 november 2026, commit f5a3136)

**Underlag och metod.** Jag har läst hela diffen `f5a3136~1..f5a3136` (11 filer, +254/−121), kört testsviten (**48 passed**) och gjort egna anrop mot produktionen 14:22–14:26 UTC samt direkta DexScreener-anrop från denna maskin med exakt samma URL och User-Agent som koden använder. Samma princip som i rond 5 och 6: ett påstående räknas först när det syns i koden eller i ett eget svar.

### Status U1–U6, T4, T5, T9

| # | Fynd | Status | Grund |
| --- | --- | --- | --- |
| U1 | Settlement före leverans | **Helt löst (dokumentation)** | `/refund` beskriver nu det faktiska flödet: kryptografisk verifiering före exekvering, settlement via facilitator och kredit/refund vid serverfel. Kodordningen i `x402.py` är oförändrad, men påståendet är inte längre osant. |
| U2 | Trending serverar fallback som färsk | **Delvis löst** | Fallbacken är korrekt märkt i live-svaret: `source: static_seed`, `data_as_of: null`, `data_age_seconds: null`, `is_stale: true`. Men live-vägen fungerar fortfarande inte i produktion: samma anrop från min maskin gav 30 par och MORPHO `927 252,85 / 242 931,78 / −2,00`, medan produktionen visar seedvärdet `521 828,24 / 172 231,95 / −1,27`. |
| U3 | Syntetiska scout-poster | **Helt löst** | WASTED levereras nu med `source: autonomous_scout_seed` och `is_synthetic: true`. Siffrorna är fortfarande påhittade, men de presenteras inte längre som marknadsdata. |
| U4 | `/status` motsäger sig själv | **Delvis löst** | Uptime är nu verklig (511 s → 620 s mellan två anrop 108 sekunder isär) och lagringssträngen är sann. Men `dexscreener: HEALTHY` visas fortfarande samtidigt som trending är `static_seed`, eftersom DEGRADED-grenen aldrig kan slå till (V2). |
| U5 | Teaser-volym | **Delvis löst** | Defaultvärdena är nu `0.0` och live-teasern visar riktiga Coinbase-volymer (146 933 723,88 USD). Kvar: volatilitetsklassningen sätter fortfarande `LOW (<1.5%)` när Parkinson-värdet är 0,0. |
| U6 | `pool_age_days` | **Delvis löst** | Åldern beräknas nu från första par med `pairCreatedAt`, men det kan vara ett annat par än det som rapporteras. VIRTUALs topp-par (Aerodrome) saknar fältet, så åldern hämtas från ett Uniswap-par skapat 2024-04-13 (≈940 dagar) i stället för seedvärdet 140 (V4). |
| T4 | Persistensen | **Kvarstår (nu ärligt redovisad)** | `render.yaml` är fortfarande `plan: free` utan `disk:`, och `DATABASE_PATH` sätts inte. Dessutom är Gist-återställningen död kod utan anropare och env-variablerna är borta — det finns ingen persistens kvar alls (V3). |
| T5 | Pass delbart / front-running | **Delvis löst** | Transaktionsåldern (900 s) verkställs nu i alla miljöer (villkoret `not settings.TESTING` är borttaget) och testas på riktigt. Kärnan kvarstår: `check_and_use_vip_pass(tx_hash, tier)` slår upp enbart på hash, utan avsändare eller signatur — medan `/refund` påstår att passet är kryptografiskt bundet till `from` (V1). |
| T9 | Gist & PII | **Helt löst** | `export_db_snapshot()` maskerar `client_ip` till `"redacted"`, `push_to_cloud_gist` maskerar en andra gång, `BACKUP_GIST_ID`/`GITHUB_BACKUP_TOKEN` är borta ur `render.yaml`, och keepalive-workflowen anropar bara `/health`, `/llms.txt` och `/agents.json`. |

### Verifierat åtgärdat

- **U1:** meningen "settled on-chain strictly AFTER ... delivers a valid HTTP 200 payload" är borta ur `/refund`. Den nya texten säger att verifiering sker före exekvering och att settlement görs av facilitorn — vilket är precis vad koden gör. Policyn stämmer nu med beteendet i stället för att lova något annat.
- **U2 (ärligheten):** fallback-svaret har `data_as_of: null` i stället för anropstiden, `data_age_seconds: null` i stället för `0`, `source: static_seed` och `is_stale: true` både på toppnivå och per tillgång. Det var rond 6:s skarpaste anmärkning och den är åtgärdad i sak.
- **U3:** `is_synthetic` och `autonomous_scout_seed` följer med WASTED-posten i live-svaret, så syntetiska tal kan inte längre förväxlas med marknadsdata.
- **U5:** `148680149.0` och `1960.2` är borta. Teaser-svaret visar faktiska Coinbase-volymer eller `0.0`, och schemaexemplet är märkt `is_schema_example` + `notice`.
- **T4 (telemetrin):** `/status` rapporterar `SQLite WAL on SSD Local Storage (/app/data/aim_network.db)` i stället för det falska "Render Persistent Disk", `coingecko_spot_fallback: STANDBY_BACKUP` och en `uptime_metric` som räknas från `app.state.started_at`. Två anrop 108 sekunder isär gav 511 s respektive 620 s — mätningen är verklig.
- **T5 (åldern):** borttagandet av `and not settings.TESTING` gör att kontrollen körs även i testmiljö, och `test_expired_transaction_rejected_by_max_age` mockar RPC:n och assertar `EXPIRED_TRANSACTION` för en två timmar gammal transfer. Det är ett beteendetest, inte en konstantkontroll.
- **T9:** PII-maskeringen sitter i `export_db_snapshot()`, alltså även för `/api/admin/backup-snapshot`, och inte bara i Gist-pusharen. Keepalive-workflowen är frikopplad från datalagring.

### Nya och kvarstående fynd (V)

**V1. Passet binds fortfarande inte till avsändaren — och `/refund` påstår motsatsen (hög).** `check_and_use_vip_pass` tar bara `tx_hash` och `tier`; `payer_address` sparas i tabellen men läses aldrig vid användning. Den som ser en tx-hash kan alltså förbruka någon annans pass, precis som i rond 6. Samtidigt säger den publika policyn: "Passes are cryptographically tied to the verified on-chain sender address (from) to prevent unauthorized pass sharing." Påståendet är falskt och står kvar trots att samma commit skrev om refundtexten. En felaktig säkerhetsgaranti i en publik policy är allvarligare än den öppna designen — den kan ligga till grund för en tvist.

**V2. `/status` kan aldrig rapportera `DEGRADED` för DexScreener (medel).** Koden sätter `dex_status = "DEGRADED" if (dex_cached and dex_cached.get("is_stale")) else "HEALTHY"`, men fallback-grenen returnerar tidigt **utan** att lägga något i cachen. `dex_cached` är därför alltid `None` när DexScreener fallerar, och statusen blir `HEALTHY`. Live-svaret bekräftar det: `dexscreener: HEALTHY` klockan 14:22:42, medan `/api/v1/trending` samma sekund svarade `static_seed`. Samma mönster finns för `coinbase_exchange_stats`, där "ingen mätning" defaultar till `HEALTHY`. En statussida som bara kan säga "friskt" är inte en statussida.

**V3. Ingen persistens kvar alls (hög).** `render.yaml` kör `plan: free` utan disk, `DATABASE_PATH` sätts inte (default `/app/data`), `restore_from_cloud_gist` och `push_to_cloud_gist` har inga anropare någonstans i `app/`, och `BACKUP_GIST_ID`/`GITHUB_BACKUP_TOKEN` är borttagna. Konsekvensen är inte bara förlorad telemetri: `used_transactions` (replay-skyddet) och `vip_passes` (kvoterna) nollställs vid varje deploy eller omstart. `/refund` lovar att hasharna "recorded atomically in SQLite to guarantee single-use consumption and prevent replay vulnerabilities across agents" — det gäller bara inom samma containerlivstid. Att städa bort Gist-kopplingen var rätt för PII, men nu finns ingen återställning alls och påståendet borde säga "per instans".

**V4. `pool_age_days` beskriver fel pool (låg).** `next((p.get("pairCreatedAt") for p in token_pairs if ...), None)` letar i alla par för tokenen, inte i det valda paret. För VIRTUAL är det valda paret Aerodrome utan `pairCreatedAt`, så åldern tas från ett Uniswap-par med helt annan likviditet. Fältet blir beräknat men syftar på en annan pool än de likviditets- och volymsiffror som rapporteras i samma post.

**V5. Ingen negativ cache och ingen synlig felorsak (låg).** Fallback-svaret cachas inte, så varje anrop till `/api/v1/trending` försöker mot DexScreener igen (uppmätt 0,61 s och 0,31 s). Felet loggas bara server-side; svaret innehåller ingen `fallback_reason` eller statuskod, så en extern agent kan inte se om seed-värdena beror på timeout, 429 eller tomt parsvar.

**V6. Pro-passet kan inte köpas — och 10 USDC ger ett Micro-pass utan Deep Report (hög).** `PRO_PASS_PRICE_USDC = 10.0` och `PRO_PASS_MAX_CALLS = 50` finns i config, men ingen route tar 10 USDC för ett pass. Den enda vägen är `verify_base_usdc_transaction(expected_amount_usdc=2.00)`, som accepterar **≥ 2 USDC**, varefter `create_vip_pass(amount_usdc=2.00, tier="premium")` anropas med hårt kodat belopp. En kund som betalar 10 USDC får alltså ett pass bokfört som 2,00 USDC med 500 mikrokvot — och `check_and_use_vip_pass` nekar premiumanrop för pass under 10 USDC, så Deep Market Report ($1,00) som Pro-passet utlovar går inte att öppna. Resten av beloppet försvinner tyst. Det betyder också att T6 från rond 6 inte är nåbar i produktion: `test_vip_pass_quota_pro_vs_micro` skapar Pro-passet direkt och bevisar bara att `create_vip_pass` räknar rätt, inte att det går att köpa.

### Svar på frågorna

**Är den standardkompatibla x402-vägen nu fullt verifierad och stabil?** Stabil på kodnivå, ja — och mer komplett än i rond 6, eftersom transaktionsåldern nu verkställs på riktigt och har ett beteendetest. Fullt verifierad är den fortfarande inte: `/status` visar 0 betalda anrop, det finns ingen settlement-transaktion, ingen BaseScan-länk och ingen replay-demonstration. Dessutom visar V6 att betalflödet har ett ohanterat beloppsglapp mellan 2 och 10 USDC. Slutsats: mekaniskt stabil, affärsmässigt oprövad.

**Kan hubben betraktas som produktionsklar för autonoma agenter?** För gratislager, discovery och schemapreview: ja. För betalande agenter: nej. Det som återstår är inte längre trovärdighetsproblem i presentationen — de är i stort sett lösta — utan fyra funktionella blockier: live-marknadsdata når inte produktionen (U2), Pro-tiern kan inte köpas och överbetalning hanteras fel (V6), passet är delbart och policyn påstår motsatsen (V1), och det finns ingen persistens så replay-skydd och kvoter nollställs vid omstart (V3).

### Uppdaterat betyg

| Område | Efter 5 | Efter 6 | Nu |
| --- | --- | --- | --- |
| Idé och discovery | 8,5 | 8,5 | 8,5 |
| Dataförtroende | 6,5 | 7,0 | 7,5 |
| Betalningsflöde | 5,5 | 6,0 | 6,0 |
| MCP-kompatibilitet | 7,5 | 7,5 | 7,5 |
| Trovärdighet/juridik | 6,5 | 6,5 | 6,5 |
| **Snitt** | **6,9** | **7,1** | **7,2** |

Dataförtroendet stiger 0,5 eftersom fallback-, färskhets- och lagringspåståendena nu är sanna och verifierbara i live-svaret. Betalningsflödet står stilla: transaktionsåldern är en reell förbättring, men V6 visar att tierlogiken inte går att använda och att 10 USDC hanteras fel — det väger upp vinsten. Trovärdigheten står också stilla: PII-exporten är borta, men den falska passbindningen i `/refund` står kvar.

### Utlåtande

Rond 7 är den rond där ärligheten blev genomförd. Fallbacken, uptimen, lagringssträngen, de syntetiska posterna och PII-exporten är nu korrekt märkta eller borttagna, och det syns i produktionssvaren — inte bara i commit-texten. Det är ett verkligt framsteg och det höjer dataförtroendet. Men granskningen hittade samtidigt ett allvarligare fel än något av de tidigare: det går inte att köpa Pro-passet, och en kund som betalar 10 USDC får ett Micro-pass som inte öppnar den rapport passet utlovar. Tillsammans med den kvarstående delningen av pass och den falska meningen i `/refund` innebär det att betalprodukten inte kan lanseras som den beskrivs. Gratis- och discovery-lagret är däremot i gott skick.

### Rekommendationer inför katalogregistrering

**Blockier före betald lansering (P0)**

1. **V6:** lägg en riktig Pro-route (10 USDC → 50 anrop, alla tiers) eller ta bort Pro-passet ur `/refund`, teasern och `llms.txt`. Acceptera aldrig `>=` utan att bokföra det faktiska beloppet: läs transferbeloppet ur receipten och skicka det till `create_vip_pass`, så att 10 USDC blir ett Pro-pass i stället för ett överbetalt Micro-pass.
2. **V1:** bind passet till avsändaren (EIP-191/ERC-1271-signatur över hash + nonce + resurs, eller sälj passet som EIP-3009-authorization) eller stryk meningen om kryptografisk bindning samma dag. En policy som beskriver ett skydd som inte finns är värre än ingen policy.
3. **V3:** välj persistens — betald disk, Postgres eller acceptera och dokumentera "per instans" — och sluta lova replay-skydd över omstarter tills det finns. Överväg att skriva ut `instance_id` i `/status` så att en agent kan se att kvoten är lokal.
4. **U2:** felsök varför DexScreener inte nås från Render (logga statuskod och svarskropp, testa samma URL från en Render-shell). Lägg en kort negativ cache så att felet inte upprepas vid varje anrop.

**Före bred katalogregistrering (P1)**

5. **V2:** sätt `UNKNOWN` i stället för `HEALTHY` när ingen mätning finns, cacha även misslyckade försök, och exponera `fallback_reason` i trending-svaret.
6. **U5 kvar:** utelämna volatilitetsklassen när Parkinson-värdet är 0,0 i stället för att kalla det "LOW (<1.5%)".
7. **V4:** rapportera `pool_age_days` från det valda paret eller utelämna fältet när `pairCreatedAt` saknas.
8. **Bevisa betalningen:** kör en riktig 0,01 USDC-betalning, visa BaseScan-länken och försök återanvända beviset från en annan IP. Publicera `total_calls_served: 1` som kvitto — först då finns underlag för betyg 8+.
9. **Kataloger:** registrera i Smithery, Glama och PayAI nu, men som gratis- och discovery-verktyg med betalflaggan märkt beta. Skruva upp marknadsföringen av betalda feeds först när punkt 1–4 är stängda.

## 17. Åttonde uppföljningen (8 november 2026, commit 0649a9f)

**Underlag och metod.** Jag har läst hela diffen `f5a3136..0649a9f` (8 filer, +342/−68), kört testsviten (**50 passed**) och gjort egna anrop mot produktionen 14:52–14:57 UTC: `/status` två gånger, `/api/v1/trending` fyra gånger inklusive ett anrop som väntade ut 60-sekunderscachen, `/api/v1/vip-pass` (utan bevis, med okänd hash och som HEAD), `/refund` som JSON och HTML, `/api/v1/free-teaser`, `/api/v1/crypto-pulse?sample=true`, `/llms.txt` och `/agents.json`. Dessutom direkta DexScreener-anrop från denna maskin med både den gamla ärliga bot-UA:n och den nya Chrome-UA:n. Samma princip som i rond 5–7: ett påstående räknas först när det syns i koden eller i ett eget svar.

### Status V1–V6, U5

| Punkt | Fynd i rond 7 | Status | Belägg |
| --- | --- | --- | --- |
| V1 | Passet inte bundet till avsändaren, medan `/refund` påstod motsatsen | **Helt löst (som påstående)** | Policyn säger nu uttryckligen "bearer tokens keyed by transaction hash with quotas tracked per container instance lifecycle", i både JSON och HTML; `/llms.txt` hänvisar korrekt till EIP-3009 för bindning |
| V2 | `/status` kunde aldrig rapportera `DEGRADED` för DexScreener | **Helt löst** | `UNKNOWN` före mätning (14:52:12), `DEGRADED` direkt efter ett trending-anrop (14:54:30); samma logik för Coinbase |
| V3 | Ingen persistens kvar, utan att det deklarerades | **Helt löst (som ärlighet)** | Live: `instance_id: inst_65f4e21e26d7` och `persistence_scope: instance-local (... resets on deployment/restart)` |
| V4 | `pool_age_days` hämtades från ett orelaterat par | **Löst i kod, ej live-verifierbart** | `chosen_pair.get("pairCreatedAt")`, annars `null`; produktionen serverar fortfarande `static_seed` med seed-värden (245/140/42) |
| V5 | Ingen negativ cache, ingen synlig felorsak | **Delvis** | 60 s negativ cache finns och `fallback_reason` exponeras — men bara på cache-miss; på cacheträffar försvinner fältet (W1) |
| V6 | Pro-passet gick inte att köpa, 10 USDC blev ett Micro-pass | **Helt löst** | `return_amount=True` läser `transferred_units / 1e6`; ≥10 USDC → Pro/50 anrop, ≥2 USDC → Micro/500; båda kvoteras i 402-svaret |
| U5 | Volatilitetsklassen "LOW (<1.5%)" vid 0,0 | **Helt löst** | `/api/v1/crypto-pulse?sample=true` returnerar `volatility_index: null` live |

### Verifierat åtgärdat

- **V6 — beloppet är verkligt nu.** `verify_base_usdc_transaction(..., return_amount=True)` returnerar `float(Decimal(transferred_units) / Decimal(1_000_000))` från den matchande `Transfer`-loggen, och `create_vip_pass` tar emot just det värdet i stället för schablonbeloppet 2,00. Gränsen går vid `transferred_usdc >= 10.00` → `pass_tier = "pro"`, `max_calls = 50`, `verified_mode = "onchain_vip_pro"`. En betalning på 10 USDC bokförs alltså som 10 USDC med 50 anrop, och `record_paid_call` får samma belopp — intäktsredovisningen stämmer nu med kedjan. Det nya testet `test_require_x402_payment_pro_pass_flow` mockar en riktig receipt med 10 000 000 mikros-USDC och assertar `tier == "pro"`, `amount_usdc == 10.0`, `max_calls == 50` och `calls_used == 1`. Det är ett beteendetest genom hela vägen, inte bara en konstantkontroll.
- **V6 — båda passen annonseras.** `build_402_response` innehåller nu `vip_24h_pass_options` med `micro_pass` (2,00 USDC / 500 anrop / mikroflöden) och `pro_pass` (10,00 USDC / 50 anrop / alla flöden inklusive Deep Market Report). Live på `/api/v1/vip-pass` returneras HTTP 402 med båda, plus den gamla `vip_24h_pass_option` för bakåtkompatibilitet. En agent kan därmed upptäcka Pro-tiern maskinläsbart, vilket den inte kunde i rond 7.
- **V6 — mikrospärren säger ifrån.** När ett Micro-pass används mot en premiumresurs returneras 402 med `"Micro VIP Pass ($2.00) does not include Premium reports ($1.00). Pro Pass ($10.00) required."` i stället för ett tyst avslag. `check_and_use_vip_pass` nekar fortfarande premiumanrop under 10,00 USDC, men nu med en begriplig orsak.
- **V1 — påståendet är borta.** `/refund` säger i både JSON och HTML att passen är bearer-tokens med kvot per containerinstans och hänvisar till standard x402/EIP-3009 för den som vill ha kryptografiskt bunden authorization. HTML-rubriken är omdöpt från "VIP Pass Wallet Binding" till "VIP Pass Bearer Tokens". `single_use_tokens` är samtidigt nedtonat till "per container instance". Jag har grepat `/`, `/refund`, `/llms.txt`, `/agents.json` och `/.well-known/x402` efter de gamla formuleringarna: enda träffen är `/llms.txt` rad 47, som säger att EIP-3009 är kryptografiskt bundet till betalarens privata nyckel — vilket är sant.
- **V2 — statusen mäter nu.** `dex_cached is None → "UNKNOWN"`, `is_stale → "DEGRADED"`, annars `"HEALTHY"`; samma trelägeslogik för Coinbase. Live 14:52:12 visade `dexscreener: UNKNOWN, coinbase_exchange_stats: UNKNOWN`; efter ett trending-anrop 14:54:30 visade samma instans `dexscreener: DEGRADED`. Det är första gången sedan rond 4 som `/status` faktiskt kan säga något annat än "friskt".
- **V3 — omfånget är deklarerat.** `app.state.instance_id = f"inst_{uuid.uuid4().hex[:12]}"` sätts i lifespan och rapporteras som `inst_65f4e21e26d7`; `persistence_scope` säger rakt ut att SQLite ligger på ephemeral container-SSD och nollställs vid deploy/omstart, och HTML-vyn visar båda fälten. Uptime räknas fortfarande från `started_at` och ökade 319 → 342 s mellan två anrop.
- **V4 och U5 — små men riktiga.** `created_at_ms = chosen_pair.get("pairCreatedAt")` med `age_days = None` när det primära paret saknar tidsstämpel, och volatilitetsklassen blir `None` när `mean_parkinson <= 0.0`. Det senare är verifierat live: sample-svaret har `volatility_index: null` i stället för `LOW (<1.5%)` med score 0,67.

### Nya fynd (W)

**W1. Cachegrenen tappar både orsaken och ärligheten (medel).** `fetch_trending_dex_tokens` har två returvägar. På cache-miss returneras hela payloaden med `fallback_reason` och `data_age_seconds: None`. På cache-träff byggs ett nytt dict med bara `tokens`, `data_as_of`, `data_age_seconds`, `source` och `is_stale` — `fallback_reason` följer inte med, och `data_age_seconds` räknas som `now - _fetched_ts`, alltså tiden sedan det misslyckade försöket, inte sedan datan observerades. Eftersom den negativa cachen nu ligger i samma cache med 60 s TTL (vilket var V5:s lösning) gäller det 59 av 60 sekunder. Bevisparet från produktionen, med 62 sekunders mellanrum:

- cache-miss: `source=static_seed, fallback_reason='DexScreener HTTP 429', data_age_seconds=None`
- cache-träff 1 s senare: `source=static_seed, fallback_reason=None, data_age_seconds=1`, och per tillgång `data_age_seconds: 48` med `data_as_of: null`

Effekten är att det svar en agent oftast får beskriver seed-data som "1 sekund gammal" utan att säga varför den är seed. Det är exakt den sortens halvsanning rond 7 städade bort, och den är tillbaka i samma fält. Åtgärden är tre rader: skicka med `fallback_reason` och sätt `data_age_seconds` till `None` när `data_as_of` är `None`.

**W2. User-Agent-maskering löser ingenting och kostar transparens (medel/låg).** Den ärliga bot-UA:n `AIMNetwork-M2M/1.1 (https://johngarp.click; ops@johngarp.click)` är ersatt av en Chrome-sträng med `Accept`- och `Accept-Language`-huvuden, uppenbart för att komma förbi Cloudflares blockering av datacenter-ASN:er. Det fungerade inte: produktionen får fortfarande `HTTP 429`, och från denna maskin ger båda UA-strängarna `200` mot samma URL, så blocken är IP-baserad och inte UA-baserad. Kvar blir att tjänsten inte längre identifierar sig för en tredje part, vilket är sämre för både DexScreeners fair-use-bedömning och för spårbarheten. En bot som döljer sig som webbläsare är också lättare att stänga av permanent än en som presenterar sig och en kontaktadress.

**W3. `/api/v1/vip-pass` kallar utgångna pass för aktiva (låg/medel).** Den nya routen hämtar passet med `get_vip_pass` och räknar `remaining = max_calls - calls_used`, men kontrollerar aldrig `expires_at`. Ett 25 timmar gammalt Pro-pass med 40 anrop kvar rapporteras som `"status": "active"` med `calls_remaining: 40`, medan `check_and_use_vip_pass` nekar exakt samma pass med utgången tid. Det är samma klass av fel som V2: en statusyta som bara kan svara positivt. Routen behöver jämföra `expires_at` mot `now` och returnera `"expired"`.

**W4. Städning (kosmetiskt).** 402-svaret innehåller både `vip_24h_pass_option` (singular, gammalt format) och `vip_24h_pass_options` (plural, nytt) med delvis överlappande information. `create_vip_pass`-docstringen säger fortfarande "up to 1,000 calls across all endpoints" trots att kvoten är 500 eller 50. `PRO_PASS_PRICE_USDC` och `PRO_PASS_DURATION_HOURS` i `config.py` används inte längre — bara `PRO_PASS_PRICE_DEC` — och passlängden tas från `VIP_PASS_DURATION_HOURS` för båda tiers. Inget av detta påverkar beteendet, men det är precis den typen av kvarlämningar som senare blir en felaktig dokumentation.

### Svar på frågorna

**Är Pro-passet nu köpbart och korrekt prissatt?** Ja, i kod och i tester. En överföring på ≥10,00 USDC ger ett Pro-pass med 50 anrop över alla flöden, inklusive Deep Market Report; en överföring på ≥2,00 USDC ger ett Micro-pass med 500 anrop på mikroflöden, och premiumförsök avvisas med ett tydligt meddelande. Beloppet som bokförs är det faktiska, inte 2,00. Det som återstår är beviset: `/status` visar fortfarande `total_calls_served: 0`, det finns ingen settlement-transaktion, ingen BaseScan-länk och ingen replay-demonstration. Mekanismen är rätt, affären är oprövad.

**Når live-marknadsdatan produktionen nu?** Nej. Produktionen får `DexScreener HTTP 429` och serverar `static_seed`, nu med korrekt källa, `is_stale` per tillgång och — en gång per minut — en korrekt orsak. Det är en ärlig fallback, inte en fungerande live-feed. Den enda kvarvarande skillnaden mot rond 7 är att felet nu går att se, vilket är värdefullt men inte samma sak som åtgärdat.

### Uppdaterat betyg

| Område | Efter 6 | Efter 7 | Nu |
| --- | --- | --- | --- |
| Idé och discovery | 8,5 | 8,5 | 8,5 |
| Dataförtroende | 7,0 | 7,5 | 7,6 |
| Betalningsflöde | 6,0 | 6,0 | 7,0 |
| MCP-kompatibilitet | 7,5 | 7,5 | 7,5 |
| Trovärdighet/juridik | 6,5 | 6,5 | 7,2 |
| **Snitt** | **7,1** | **7,2** | **7,6** |

Betalningsflödet stiger 1,0: V6 var ett hål där kunder kunde betala 10 USDC och få en produkt de inte kunde använda, och det är nu stängt i både kod, test och prislista. Det som håller betyget under 7,5 är frånvaron av ett enda verifierat betalflöde i produktion. Dataförtroendet går upp marginellt: `/status` och volatiliteten är nu sanna, men W1 visar att fallback-svaret fortfarande kan beskriva seed-data som ett sekund gammal. Trovärdigheten stiger 0,7 eftersom den falska bindningen är borta och instansomfånget är deklarerat — det var de två påståenden som kunde bli en tvist.

### Utlåtande

Rond 8 stänger den värsta kvarvarande defekten. Pro-passet går att köpa, beloppet som bokförs är det som faktiskt överfördes, båda tiers annonseras maskinläsbart, och mikrospärren säger ifrån i stället för att tiga. Tillsammans med den rättade `/refund`-texten och den ärliga instansdeklarationen innebär det att plattformen inte längre lovar något den inte gör — med ett undantag, W1, där cachegrenen återinför precis den halvsanning som rond 7 tog bort.

Det som nu skiljer AIM Network från en produktionsklar betaltjänst är inte längre trovärdighet utan två konkreta saker: flagship-feeden levererar fortfarande seed-data i produktion eftersom DexScreener blockerar Render, och ingen betalning har någonsin genomförts och kvitterats. Båda är mätbara och båda är åtgärdbara. Registrering i agentkataloger är därför försvarbar nu för gratis- och discovery-lagret, och försvarbar som beta för betalning — men inte som en bevisat fungerande betalprodukt.

### Rekommendationer inför katalogregistrering

**Blockier före betald lansering (P0)**

1. **W1:** skicka med `fallback_reason` i cachegrenen och sätt `data_age_seconds: None` när `data_as_of` är `None`. Tre rader, och det gör att rond 7:s viktigaste fix gäller alla svar i stället för ett per minut.
2. **DexScreener 429:** lös blocken på riktigt — egen proxy/egress med accepterad IP, en alternativ DEX-datakälla (GeckoTerminal, Birdeye eller egen RPC-läsning av poolkontrakten), eller acceptera seed-läget och sälj inte trending som live. UA-maskering är ingen lösning; se W2.
3. **W3:** kontrollera `expires_at` i `/api/v1/vip-pass` och returnera `"expired"` med `calls_remaining: 0`.
4. **Betalbevis:** kör en riktig betalning på 0,01 USDC (eller 2,00 för ett Micro-pass), publicera BaseScan-länken, försök återanvända beviset från en annan IP och visa `total_calls_served: 1`. Först då finns underlag för att kalla betalflödet verifierat.

**Före bred marknadsföring (P1)**

5. **W2:** återställ den ärliga bot-UA:n med kontaktadress. Den kostar ingenting och är det enda som skiljer en seriös integration från en scraper.
6. **W4:** ta bort den gamla `vip_24h_pass_option`, rätta docstringen till 500/50 anrop och städa de oanvända Pro-konstanterna.
7. **Mikro vs Pro:** 10 USDC ger 50 anrop medan 2 USDC ger 500 — det är försvarbart som premiumscop, men skriv ut det explicit i `/refund` ("färre anrop, alla flöden") så att det inte läses som ett pris fel.
8. **Kataloger:** registrera i Smithery, Glama och PayAI nu som gratis- och discovery-verktyg med betalflaggan märkt beta, och skruva upp betalmarknadsföringen först när punkt 1–4 är stängda.

## 18. Nionde uppföljningen (8 november 2026, commit a3af5c2)

**Underlag och metod.** Jag har läst hela diffen `0649a9f..a3af5c2` (6 filer, +85/−16), kört testsviten (**52 passed**) och gjort egna anrop mot produktionen 15:11–15:18 UTC: `/status` två gånger, `/api/v1/trending` fem gånger inklusive ett anrop som väntade ut 60-sekunderscachen, `/api/v1/vip-pass`, fyra dynamiska endpoints (`morpho`, `virtual`, `wasted`, `airdrop`) samt direkta DexScreener-anrop med samma User-Agent och URL som koden använder. Samma princip som i rond 5–8: ett påstående räknas först när det syns i koden eller i ett eget svar.

**Det viktigaste i den här ronden stod inte i commit-beskrivningen:** produktionen levererar nu live-data. Första trending-anropet svarade `source: dexscreener_base_live` med `data_as_of: 2026-11-08T15:14:38Z` i stället för `static_seed`, och värdena stämmer exakt med DexScreener (MORPHO 984 877,14 / 299 740,5 / −1,99 och VIRTUAL 864 552,34 / 1 018 619,18 / −1,22 i båda källorna). Den 429-blockering som låg fast i rond 7 och 8 är alltså borta, och `/status` visar följaktligen `dexscreener: HEALTHY`. Det betyder också att V4 nu går att verifiera live för första gången.

### Status W1–W4

| Punkt | Fynd i rond 8 | Status | Belägg |
| --- | --- | --- | --- |
| W1 | Cachegrenen tappade `fallback_reason` och hittade på `data_age_seconds` | **Helt löst** | `age_seconds = None if is_stale else ...` och `fallback_reason` följer med i returen; `test_trending_dex_tokens_cache_preserves_fallback_and_null_age` assertar båda. Live kan inte längre trigga fallet eftersom fallbacken inte inträffar |
| W2 | Chrome-UA mot DexScreener dolde tjänsten utan att lösa 429 | **Helt löst** | Ärlig UA återställd i `headers`; produktionen får nu `200` och live-data, så blocken var IP-baserad och har släppt |
| W3 | `/api/v1/vip-pass` kallade utgångna pass "active" | **Helt löst, med kvarstående inkonsekvens** | `expires_dt` jämförs mot `now`, `is_expired` returneras; `test_vip_pass_endpoint_expiry_status` backdaterar `expires_at`. Men `calls_remaining` nollställs inte vid utgång |
| W4 | Dubblerad 402-nyckel, fel docstring, oanvända Pro-konstanter | **Delvis löst** | `vip_24h_pass_option` är borta ur live-svaret och docstringen säger 500/50; `PRO_PASS_PRICE_USDC` och `PRO_PASS_DURATION_HOURS` finns kvar oanvända i `config.py` |

### Verifierat åtgärdat

- **W1 — cachegrenen är nu hel.** `is_stale` läses först, `age_seconds` blir `None` när datan är stale, `data_as_of` hämtas med `.get()` och `fallback_reason` följer med i svaret. Testet lägger in en stale payload i cachen och assertar `is_stale`, `source`, `data_as_of is None`, `data_age_seconds is None` och `fallback_reason == "DexScreener HTTP 429"`. Den enda reservationen är att det inte gick att verifiera live, eftersom DexScreener nu svarar 200: fallback-vägen är helt enkelt inte längre aktiv. Det är ett bra skäl att inte kunna reproducera felet i produktion.
- **W2 — identifieringen är återställd.** Headern är tillbaka till `AIMNetwork-M2M/1.1 (https://johngarp.click; ops@johngarp.click)` med `Accept: application/json`. Produktionen hämtar nu live-data, vilket samtidigt bevisar att Chrome-maskeringen i rond 8 var verkningslös: samma endpoint, samma IP, nu 200 med den ärliga UA:n.
- **W3 — utgången kontrolleras.** `expires_dt = datetime.fromisoformat(pass_data["expires_at"])`, `is_expired = now >= expires_dt`, och statusen blir `"expired"`, `"exhausted"` eller `"active"` i den ordningen. Svaret innehåller `is_expired` som ett explicit fält, så en agent slipper tolka statussträngen. Testet skapar ett pass, backdaterar `expires_at` en timme och assertar `status == "expired"` och `is_expired is True` över HTTP.
- **W4 — 402-strukturen är ren.** Live-svaret på `/api/v1/vip-pass` innehåller `payment_details` med nycklarna `network, chain_id, token, token_contract, amount, recipient, description, vip_24h_pass_options` — ingen `vip_24h_pass_option` längre. Jag har grepat hela repot och alla publika ytor (`/llms.txt`, `/agents.json`): ingen konsument refererade den gamla nyckeln, så borttagningen är inte brytande i praktiken. Docstringen säger nu "500 calls for Micro, 50 calls for Pro".
- **V4 — nu verifierad live.** Eftersom trending-feeden är live kan jag äntligen kontrollera fältet på riktigt: MORPHO och VIRTUAL rapporterar `pool_age_days: null`, och DexScreener bekräftar att det valda Aerodrome-paret saknar `pairCreatedAt` (medan Uniswap-paren har 1731367701000 respektive 1712965679000). Åldern lånas alltså inte längre från en orelaterad pool. Fixen är korrekt — men den lämnar metern tom, se X3.
- **V2 — trelägesstatusen fungerar i båda riktningarna.** Före ett trending-anrop visade `/status` `dexscreener: UNKNOWN`, efter ett anrop `HEALTHY` — samma instans, samma kod, bara olika mätläge. Det är exakt det beteende som efterlystes i rond 7 och som saknades i rond 8:s bevisning (då syntes bara UNKNOWN → DEGRADED).

### Nya fynd (X)

**X1. De annonserade tillgångsendpoints som discovery pekar på svarar 404 (medel).** Det fria trending-svaret innehåller för varje tillgång `endpoint_path` och `sample_url`, och för de två flagship-tillgångarna pekar de på `/api/v1/trending/morpho` respektive `/api/v1/trending/virtual`. Båda svarar **404** med `"Dynamic endpoint /api/v1/trending/morpho not found."` Även ett påhittat `airdrop` ger 404, medan `/api/v1/trending/wasted` fungerar som det ska (402 utan bevis, 200 med `?sample=true`). Orsaken är att routen `get_dynamic_trending_endpoint` slår upp `slug` i tabellen `dynamic_endpoints`, och den tabellen fylls bara av den autonoma scouting-loopen — de kanoniska MORPHO- och VIRTUAL-posterna i payloaden är hårdkodade och registreras aldrig. Konsekvensen är att en agent som följer den kostnadsfria discovery-listan till den endpoint som listas får ett fel i stället för ett pris. Det är den viktigaste kvarvarande defekten för katalogregistrering, eftersom det är precis det flöde en katalog gör: lista, klicka, betala. Två rimliga fixar: registrera de kanoniska slugarna i `dynamic_endpoints` vid uppstart, eller låt `/trending/{slug}` servera live-marknadsdata direkt för kända slugar utan databaskrav.

**X2. Syntetiska poster får live-tidsstämpel (låg).** WASTED-posten har `source: autonomous_scout_seed` och `is_synthetic: true`, men får samma `data_as_of: 2026-11-08T15:14:38Z` och `data_age_seconds: 31` som de riktiga live-tillgångarna, trots att siffrorna (124 850,2 / 48 900,5 / 2,45) är hårdkodade. Nu när två av tre poster är live blir kontrasten tydlig: en agent som filtrerar på `data_age_seconds` får en seed-post som ser lika färsk ut som marknadsdata. `is_synthetic` räddar det formellt, men tidsstämpeln bör vara `null` för syntetiska poster, precis som rond 7 gjorde för fallbacken.

**X3. `pool_age_days` är tom i produktion (låg).** V4-fixen är korrekt, men effekten är att båda live-tillgångarna rapporterar `null` för ett fält som beskrivs som "Days elapsed since primary liquidity pair deployment on Base L2". Aerodrome-paren som DexScreener väljer har inget `pairCreatedAt`, så metern är alltid tom för de två viktigaste tillgångarna. Bättre vore att ta `pairCreatedAt` från det högst likvida paret som faktiskt har ett tidsstämpel (Uniswap-paren har det) och ange i `pool_age_metric` att åldern då avser en sekundär pool — eller att ta bort fältet ur prislistan.

**X4. Kvarlämningar (kosmetiska).** `dex` blir `"Aero / Base"` i live-läget (DexScreener rapporterar `dexId: "aero"`, som `.capitalize()` gör om) men `"Aerodrome / Base"` i seed-läget — samma börs, två namn. W3:s `calls_remaining` returneras oförändrat för ett utgånget pass, så svaret kan säga `"status": "expired"` och `calls_remaining: 499` samtidigt. W4:s `PRO_PASS_PRICE_USDC` och `PRO_PASS_DURATION_HOURS` är fortfarande oanvända. Ingen av dessa påverkar ett maskinellt beslut, men de är billiga att städa och de syns i publika svar.

### Svar på frågorna

**Levererar plattformen live-marknadsdata nu?** Ja. Det var rond 7–8:s största öppna fråga och den är stängd: `source: dexscreener_base_live`, `data_as_of` satt, `is_stale: false` per tillgång och värden som matchar källan på centnivå. Fallbacken finns kvar och är nu korrekt märkt i båda sina lägen. Det som återstår är inte datakvalitet utan att de endpoints som discovery pekar på måste svara (X1).

**Är betalflödet verifierat?** Nej, fortfarande inte. Koden är nu konsistent — Pro-pass, faktiskt belopp, utgångskontroll, ren 402-struktur — och 52 tester täcker mekaniken, men `/status` visar `total_calls_served: 0`. Ingen betalning har genomförts, ingen settlement-transaktion finns och ingen replay-demonstration är gjord. Det är den enda kvarvarande punkten där jag inte kan ersätta ett test med ett live-bevis.

### Uppdaterat betyg

| Område | Efter 7 | Efter 8 | Nu |
| --- | --- | --- | --- |
| Idé och discovery | 8,5 | 8,5 | 8,5 |
| Dataförtroende | 7,5 | 7,6 | 8,2 |
| Betalningsflöde | 6,0 | 7,0 | 7,2 |
| MCP-kompatibilitet | 7,5 | 7,5 | 7,5 |
| Trovärdighet/juridik | 6,5 | 7,2 | 7,3 |
| **Snitt** | **7,2** | **7,6** | **7,7** |

Dataförtroendet stiger 0,6 — det är rondens stora förändring. Feeden levererar verklig marknadsdata som matchar källan, tidsstämpeln är sann, `is_stale` sätts per tillgång och statusen växlar korrekt mellan UNKNOWN, HEALTHY och DEGRADED. Det som håller det under 8,5 är X1: den data som säljs nås inte via den väg discovery annonserar. Betalningsflödet går upp 0,2 för utgångskontrollen och den rena 402-strukturen, men står kvar på 7,2 eftersom inget betalbevis finns. Trovärdigheten går upp marginellt: den ärliga UA:n är tillbaka och fallbacken är hel i båda lägen, medan X2 visar att en syntetisk post fortfarande kan se färsk ut.

### Utlåtande

Rond 9 är vändpunkten för datalagret. Efter tre ronder där flagship-feeden serverade seed-värden i produktion levererar den nu live-data, med en tidsstämpel som stämmer, en statusflik som stämmer och en fallback som är korrekt märkt i alla lägen — inklusive cacheträffarna. Tillsammans med den återställda User-Agenten, utgångskontrollen på passen och den städade 402-strukturen är W1–W3 stängda och W4 nästan.

Det som återstår är av två slag. Det ena är mekaniskt och litet: X1, att de endpoints som det fria discovery-svaret pekar på måste svara. Det är en missvisande länk i kärnflödet och den bör åtgärdas innan registrering, annars möter en katalog ett 404 där den förväntar sig ett pris. Det andra är affärsmässigt och större: ingen betalning har någonsin genomförts, så hela betalflödet vilar fortfarande på tester och kodläsning. Gratis- och discovery-lagret är i gott skick och kan registreras nu; betalflaggan bör sättas till beta tills ett riktigt betalbevis finns.

### Rekommendationer inför katalogregistrering

**Blockier före registrering (P0)**

1. **X1:** se till att varje `endpoint_path` som listas i `/api/v1/trending` svarar. Registrera de kanoniska slugarna i `dynamic_endpoints` vid uppstart eller låt `/trending/{slug}` serva kända assets direkt ur live-datan. Ett enkelt regressionstest: hämta `/api/v1/trending`, plocka varje `sample_url` och asserta 200.
2. **Betalbevis:** kör en riktig betalning — 0,01 USDC för ett mikrocall eller 2,00 USDC för ett Micro-pass — publicera BaseScan-länken, försök återanvända beviset från en annan IP och visa att `total_calls_served` räknas upp. Det är den sista pusselbiten som skiljer "testad kod" från "fungerande tjänst".
3. **W3-rest:** sätt `calls_remaining: 0` (eller utelämna fältet) när `is_expired` är sant, så att status och kvot inte kan läsas som motstridiga.

**Före bred marknadsföring (P1)**

4. **X2:** sätt `data_as_of` och `data_age_seconds` till `null` för poster med `is_synthetic: true`, så att bara verkligt observerad data får en färskhet.
5. **X3:** fyll `pool_age_days` från det högst likvida paret med `pairCreatedAt`, och skriv i `pool_age_metric` att fältet då avser den poolen — eller ta bort fältet ur beskrivningen.
6. **W4-rest:** ta bort `PRO_PASS_PRICE_USDC` och `PRO_PASS_DURATION_HOURS` eller använd dem, så att config är den enda sanningen om pris och löptid.
7. **X4:** normalisera `dex` till ett namn per börs ("Aerodrome / Base" även live).
8. **Kataloger:** registrera i Smithery, Glama och PayAI nu som gratis- och discovery-verktyg. Sätt betalflaggan till beta och skriv ut att Pro-pass krävs för Deep Market Report, så att en agent inte köper ett Micro-pass och möter ett 402.

## 19. Tionde uppföljningen (8 november 2026, commit eb12f3e)

**Underlag och metod.** Jag har läst hela diffen `a3af5c2..eb12f3e` (6 filer, +123/−13), kört testsviten (**54 passed**) och gjort egna anrop mot produktionen 15:35–15:40 UTC: `/api/v1/trending` tre gånger i följd, `/status`, `/health`, `?sample=true` på `morpho`, `virtual` och `dacity`, oskyddat anrop på `morpho` och `wasted`, samt ett direkt DexScreener-anrop med samma URL och User-Agent som koden. Dessutom har jag reproducerat den betalda kanoniska vägen i en lokal sandbox (`TESTING=true`, `X402_VERIFY_MODE=hybrid`, temporär SQLite), både med live-feed och med tvingad fallback-feed. Samma princip som tidigare: ett påstående räknas först när det syns i koden eller i ett eget svar.

**Nyckelfakta vid granskningstillfället.** Instansen var ny — `instance_id inst_fc9d95f50614`, uptime 281–295 s — och `/status` visar `"dexscreener": "DEGRADED"`. Trending-feeden svarar `source: static_seed` med `fallback_reason: "DexScreener HTTP 429"` i tre anrop över tolv sekunder, alltså även efter att 60-sekunderscachen löpt ut. Samtidigt svarar DexScreener **200** på exakt samma endpoint från min egen IP. Felet sitter alltså i Render-instansens utgående IP, inte hos DexScreener globalt. Att `/status` ändå rapporterar `DEGRADED` och att varje post har `is_stale: true` är korrekt och hederligt — W1-fixen fungerar i skarpt läge, vilket den inte kunde bevisas göra i rond 9.

### Status X1–X4 och W3/W4-rester

| Punkt | Fynd i rond 9 | Status | Belägg |
| --- | --- | --- | --- |
| X1 | `/trending/morpho` och `/trending/virtual` svarade 404 | **Löst** | Båda svarar `200` med `SAMPLE_DATA_VERIFIED` och `symbol: MORPHO`/`VIRTUAL`; oskyddat anrop ger `402` med `amount: "0.05"`. Kanonisk träff slås nu upp i trending-feeden före databasen |
| X2 | Syntetiska poster ärvde live-tidsstämpel | **Löst** | `dacity` (den syntetiska posten) har `is_synthetic: true` med `data_as_of: null` och `data_age_seconds: null`; koden sätter `None` explicit i stället för feedens stämpel |
| X3 | `dex` hette "Aero / Base" live | **Löst i kod, delvis verifierat** | Fallback-vägen ger `"Aerodrome / Base"`; live-vägen mappar `aero`/`aerodrome` till samma sträng. Live-läget kunde inte observeras eftersom 429:an sammanföll med granskningen |
| W3-rest | `calls_remaining` nollställdes inte vid utgång | **Löst i kod och test** | `remaining = 0 if is_expired else ...`; `test_vip_pass_endpoint_expiry_status` täcker gränsfallet. Inget utgånget pass finns i produktionen, så live-bevis saknas |
| W4-rest | Två oanvända Pro-konstanter | **Delvis löst** | `PRO_PASS_PRICE_USDC` är borta och `PRO_PASS_DURATION_HOURS` styr nu löptiden i `database.py`. Men Pro-tröskeln ligger kvar som hårdkodad `10.0` på fem ställen i `database.py`/`x402.py` |

### Verifierat åtgärdat

- **X1, verifierat live:** de två kanoniska slugarna svarar nu i båda lägena. `?sample=true` ger `200` med `status: SAMPLE_DATA_VERIFIED`, `symbol: MORPHO` respektive `VIRTUAL` och `live_price_usdc: 0.05`; utan bevis ges `402` med oförändrad prisstruktur. Den tredje postens `sample_url` (`/api/v1/trending/dacity?sample=true`) svarar också `200`. Varje länk som den fria listan annonserar fungerar därmed vid granskningstillfället — det var rond 9:s huvudanmärkning.
- **X2, verifierat live:** `dacity` bär `is_synthetic: true` och har `data_as_of: null` jämte `data_age_seconds: null`. Ingen syntetisk post kan längre se färsk ut, och de två riktiga tillgångarna har `is_stale: true` när fallbacken är aktiv.
- **X3/X4, verifierat i fallback och i kod:** `dex` är `"Aerodrome / Base"` i produktionssvaret, och live-grenen mappar både `aero` och `aerodrome` till samma sträng i stället för att förlita sig på `.capitalize()`.
- **W3-rest, verifierat i kod och test:** kvoten tvingas till `0` när `is_expired` är sant.
- **W4-rest, delvis:** `PRO_PASS_PRICE_USDC` är borta ur `config.py` och `PRO_PASS_DURATION_HOURS` används nu aktivt i `create_vip_pass`.
- **Ärligheten från rond 7–9, verifierat i skarpt läge:** nu när upstream faktiskt fallerar syns hela kedjan — `fallback_reason` bevaras, `data_as_of` sätts till `null`, `is_stale: true` per post, `/status` visar `DEGRADED`. Det var precis det som inte gick att prova när feeden fungerade.

### Nya fynd (Y)

**Y1. Live-feeden slås ut av 429 mot Render-instansens IP (medel).** Vid granskningen svarade `/api/v1/trending` `static_seed` med `fallback_reason: "DexScreener HTTP 429"` i tre anrop över tolv sekunder, medan samma endpoint med samma URL och User-Agent gav `200` från min egen IP. `/status` visar `dexscreener: DEGRADED`. Det betyder att rond 9:s `HEALTHY` inte var stabilt: live-läget är beroende av vilken utgående IP Render-instansen råkar få, och DexScreener stryper delade moln-IP:er. Konsekvensen är att en agent som betalar under ett sådant fönster får seedvärden, och att nyttan av hela live-arkitekturen blir intermittent utan att någon kod är fel. Rimliga motmedel: retry med backoff i stället för en enda förfrågan, byte till `tokens/v1/{chain}/{address}`-endpointen som svarade `200`, eller att behålla senast kända live-värden med ålder i stället för att falla till seed.

**Y2. Betald kanonisk hämtning kan leverera seed-data utan stale-flagga (medel).** I sandboxen ger ett betalt anrop till `/api/v1/trending/morpho` `200` med `meta.source: static_seed` och `meta.as_of: null`, men `asset` innehåller varken `is_stale` eller `is_synthetic` — nycklarna finns helt enkelt inte i den kanoniska svarsmodellen. Den fria feeden flaggar varje post, den betalda gör det inte. En agent som betalar $0.05 och läser `asset` får alltså hårdkodade 984 877,14 / 299 740,5 / −1,99 utan att någonstans i objektet se att de är statiska. `meta.source` avslöjar det indirekt, men det är en svagare garanti än den fria feedens explicita flagga, och asymmetrin är omvänd mot vad som är rimligt: ju mer data kostar, desto tydligare bör dess kvalitet deklareras.

**Y3. Per-tillgångsstatistik skrivs aldrig för kanoniska slugar (låg).** `increment_dynamic_endpoint_stats` gör en `UPDATE` på raden med matchande slug, men de kanoniska tillgångarna finns inte i `dynamic_endpoints` — de skapas i koden, inte i databasen. Resultatet är en tyst no-op: efter ett betalt anrop till `/api/v1/trending/morpho` i sandboxen redovisar `get_stats` `total_calls: 1` och `recent_transactions` med rätt post, men `dynamic_endpoints: []`. Ingen `calls_count` och ingen `revenue_usdc` ackumuleras alltså för de två viktigaste säljande endpointsen. Det syns också i dashboardens formulering om "extra trend-API:er", som bara räknar databasrader.

**Y4. Pro-tröskeln är fortfarande hårdkodad (låg).** W4-resten är bara delvis stängd: konstanten `PRO_PASS_PRICE_USDC` är borta, men talet den uttryckte lever kvar som `10.0` på fem ställen (`database.py` raderna 467, 499, 520 samt `x402.py` 403, 438) bredvid `PRO_PASS_PRICE_DEC = Decimal("10.00")`. Ändras priset i config ändras alltså inte Pro-gränsen, och en Pro-betalning på 9,99 USDC skulle fortfarande behandlas som Micro. Det är samma klass av fel som W4 anmärkte, bara flyttat från config till affärslogik.

**Y5. Scout-länkar är flyktiga (information).** Vid granskningen hette den tredje posten `dacity` i stället för `wasted`, och `/api/v1/trending/wasted` svarade `404`. Orsaken står i `/status` självt: `persistence_scope: "instance-local (SQLite WAL on ephemeral container SSD; resets on deployment/restart)"`. Varje deploy nollställer databasen, så scouting-loopens endpoints och all räkenskapsdata försvinner medan de kanoniska posterna består. En katalog som cachar en scout-URL från förra veckan får 404, och `total_calls_served` börjar om på noll vid varje deploy — vilket gör det omöjligt att visa ackumulerad trafik i en katalogstatistik.

### Svar på frågorna

**Fungerar de annonserade endpointsen nu?** Ja. Rond 9:s blockerare är stängd: varje `sample_url` som den fria listan innehåller svarar `200`, och de kanoniska slugarna ger dessutom korrekt `402` med fullständiga betalningsdetaljer. Det var det enda som återstod för att ett katalogflöde "lista, klicka, betala" skulle hålla hela vägen fram till betalningen.

**Är live-datan tillförlitlig?** När den är live, ja — värdena matchar källan och markörerna är korrekta i alla lägen. Tillgängligheten är däremot inte tillförlitlig: samma instans som gav `HEALTHY` i rond 9 gav `DEGRADED` nu, och felet ligger i Render-IP:n, inte i koden. Det är en driftsfråga som måste lösas innan live-data kan kallas en garanti i en katalogbeskrivning.

**Är betalflödet verifierat?** Nej. `total_calls_served` är fortfarande `0`, ingen settlement-transaktion finns och inget riktigt anrop har gått genom x402-verifieringen mot Base. Koden är nu testad i 54 fall och 402-strukturen är korrekt, men det är fortfarande mekanik, inte bevis.

### Uppdaterat betyg

| Område | Efter 8 | Nu |
| --- | --- | --- |
| Idé och discovery | 8,5 | 8,8 |
| Dataförtroende | 8,2 | 8,0 |
| Betalningsflöde | 7,2 | 7,4 |
| MCP-kompatibilitet | 7,5 | 7,5 |
| Trovärdighet/juridik | 7,3 | 7,5 |
| **Snitt** | **7,6** | **7,8** |

Discovery-betyget stiger 0,3 för att den blockerare som höll det kvar är stängd och för att varje annonserad länk nu svarar. Dataförtroendet faller 0,2 trots att X2–X4 är åtgärdade: markörerna är bättre, men live-vägen visade sig vara IP-beroende och betald data kan fortfarande vara seed utan flagga. Betalningsflödet går upp 0,2 eftersom betalvägen nu faktiskt existerar för de tillgångar som säljs. Trovärdigheten går upp 0,2 — `/status` är öppen om både `DEGRADED` och den efemära lagringen.

### Utlåtande

Rond 10 stänger den blockerare som har legat överst i tre ronder. De endpoints som discovery pekar på svarar, i både gratis och betalt läge, och den syntetiska posten kan inte längre förväxlas med marknadsdata. Det betyder att den kedja en katalog faktiskt prövar — lista, följ länken, få ett pris — nu håller hela vägen fram till betalningen.

Det som håller betyget under 8 är inte längre ett logikfel utan två villkor. Det första är tillgänglighet: live-feeden föll tillbaka till seed på grund av 429 mot Render-IP:n, medan samma anrop lyckades från en annan adress. Koden hanterade det korrekt och ärligt, men en agent som betalar i det fönstret får statiska tal. Det andra är att betalflödet fortfarande aldrig har setts med riktiga pengar; `total_calls_served: 0` gäller även efter den här ronden.

Min bedömning är att gratis- och discovery-lagret kan registreras i Smithery, Glama och PayAI nu — den vägen är verifierad hela vägen. Betaldelen bör sättas till beta tills Y2 är åtgärdad och ett riktigt betalbevis finns, eftersom det är där en agent kan betala för data som inte är live utan att få det sagt i själva svaret.

### Rekommendationer

**Före registrering av betaldelen (P0)**

1. **Y2:** lägg `is_stale` och `is_synthetic` i den betalda kanoniska `asset`-modellen, och överväg att avvisa betalda anrop med `503` när feeden är `static_seed` i stället för att leverera seed-värden. Ett test som tvingar fallback och assertar flaggan räcker.
2. **Betalbevis:** en riktig betalning på 0,01 eller 0,05 USDC, BaseScan-länk, ett replay-försök från annan IP, och en skärmbild av att `total_calls_served` räknas upp. Det är fortfarande den enda punkten där test inte kan ersätta drift.
3. **Y1:** byt till `tokens/v1/{chain}/{address}` eller lägg retry med backoff, och behåll senast kända live-värden med ålder i stället för att falla direkt till seed. Ett `DEGRADED` som varar i timmar är i praktiken ett seed-läge med extra steg.

**Före bred marknadsföring (P1)**

4. **Y3:** registrera kanoniska slugar i `dynamic_endpoints` vid uppstart, eller gör `increment_dynamic_endpoint_stats` till en upsert, så att per-tillgångsintäkter syns.
5. **Y4:** ersätt de fem `10.0` med `settings.PRO_PASS_PRICE_DEC`, så att pris och Pro-gräns inte kan glida isär.
6. **Y5:** flytta SQLite till en persistent volym, eller återregistrera scout-slugarna vid uppstart, så att katalogcachade länkar inte dör vid deploy och trafiksiffror kan ackumuleras.
7. **Kataloger:** registrera gratis- och discovery-lagret nu, med betalflaggan som beta och en tydlig upplysning om att Pro-pass krävs för Deep Market Report.

## 20. Elfte uppföljningen (8 november 2026, commit 3379eac)

**Underlag och metod.** Granskningen omfattar hela diffen `eb12f3e..3379eac` (6 filer, +386/−34), lokal körning av hela testsviten (**58 passed** på 30,56 s), riktad reproduktion av `_FakeAsyncClient` mot `fetch_trending_dex_tokens`, samt live-anrop mot `https://johngarp.click` mellan 16:00:37 och 16:04:36 UTC på instansen `inst_20a851a17458` (`/status`, `/api/v1/trending` före och efter 60 s cache-TTL, `/api/v1/trending/morpho`, `/virtual` och `/wasted` med och utan `?sample=true`, `/api/v1/base-dex-radar`, `/llms.txt`, `/agents.json`, `POST /mcp` med `tools/call` `list_trending_assets` samt direkt kontroll mot `https://api.dexscreener.com/tokens/v1/base/...`).

**Avgörande live-bevis under granskningen.** Det som Freebuff inte hann observera direkt vid deploy (`uptime: 18 s`, då instansen ännu saknade en första live-observation och svarade `static_seed` / `503`) inträffade skarpt på exakt samma instans (`inst_20a851a17458`) några minuter senare:
1. **16:00:38 UTC (`uptime: 353 s`) — Live-träff:** DexScreener släppte igenom instansen. `/api/v1/trending` svarade `source: "dexscreener_base_live"`, `data_as_of: "2026-11-08T16:00:38.715109+00:00"`, `data_age_seconds: 0`, `fallback_reason: null`, `is_stale: false` (`morpho`: `liquidity_usd: 1040504.79`, `volume_24h_usd: 276183.15`, `momentum_24h_pct: -1.11`; `virtual`: `liquidity_usd: 895404.67`, `volume_24h_usd: 995812.35`, `momentum_24h_pct: -0.79`). Samtidigt växlade `/status` till `"dexscreener": "HEALTHY"`, och `/api/v1/trending/morpho` samt `/virtual` övergick från `503` till `402 Payment Required` (`amount: "0.05"`).
2. **16:03:55 UTC (`uptime: 553 s`) — Övergång till `last_good` vid ny 429:** När 60-sekunderscachen löpt ut och DexScreener åter svarade HTTP 429 föll instansen **inte** tillbaka till `static_seed`, utan aktiverade Y1 i skarpt läge: `source: "dexscreener_base_live_last_good"`, `data_as_of: "2026-11-08T16:00:38.715109+00:00"`, `data_age_seconds: 197`, `fallback_reason: "DexScreener HTTP 429"` och `is_stale: true` på `morpho` och `virtual` (med de verkliga värdena från 16:00:38 bevarade), medan `/status` växlade till `"dexscreener": "DEGRADED"`.
3. **16:04:20 UTC — Cache-träff i `last_good`-läge:** Ett nytt anrop 25 sekunder senare (inom 60 s-cachen) svarade `data_age_seconds: 222` med bibehållen `fallback_reason: "DexScreener HTTP 429"`. `_observed_ts` räknar alltså åldern från det faktiska observationstillfället även vid cacheträffar.

### Status Y1–Y5

| Punkt | Fynd i rond 10 | Status | Belägg |
| --- | --- | --- | --- |
| Y1 | 429 mot Render-IP slog ut live-feeden till `static_seed` | **Helt löst (verifierat live)** | Dubbla endpoints (`latest/dex/tokens` + `tokens/v1/base`) med retry och `_last_good_live` (6 h TTL). Både `dexscreener_base_live` (16:00:38 UTC) och `dexscreener_base_live_last_good` (`age: 197` → `222`) verifierade live på `inst_20a851a17458` |
| Y2 | Betald kanonisk väg saknade stale-flaggor och kunde sälja seed | **Delvis löst** | Kanoniska slugar har nu `is_stale`/`is_synthetic` i `asset` och `meta`, och `source == "static_seed"` stoppas med `503 DATA_QUALITY_UNAVAILABLE` (`Retry-After: 60`). Men scout-slugar (`/trending/wasted`) och `/base-dex-radar` saknar samma spärr (se Z1) |
| Y3 | Per-tillgångsstatistik skrevs aldrig för kanoniska slugar | **Helt löst** | `_bootstrap_canonical_endpoints` registrerar `morpho`/`virtual` vid uppstart och `increment_dynamic_endpoint_stats` har upsert-fallback (`cursor.rowcount == 0`). Verifierat i test (`calls_count == 1`, `revenue_usdc == 0.05`) |
| Y4 | Pro-tröskeln låg kvar som hårdkodad `10.0` på fem ställen | **Helt löst** | Samtliga fem kontroller i `app/database.py` (rad 489, 525, 548) och `app/x402.py` (rad 403, 444) samt prisfält i felmeddelanden läser nu `settings.PRO_PASS_PRICE_DEC`. Testtäckt med monkeypatch till `12.00` |
| Y5 | Kanoniska/scoutade slugar och listor påverkades av DB-reset | **Delvis löst** | `_bootstrap_canonical_endpoints` gör att `POST /mcp` (`list_trending_assets`), `/llms.txt` och `/agents.json` nu listar `morpho`, `virtual` och `wasted` direkt efter omstart. Efemär disk kvarstår dock, och prune-gränsen har en kantbugg (se Z4) |

### Nya fynd i commit `3379eac` (Z = rond 11)

**Z1. `503`-spärren och `is_stale`-flaggorna gäller bara kanoniska slugar — scout-endpoints och `/base-dex-radar` säljer fortfarande hårdkodad fallback-data (medel).** I `app/routers/api_v1.py:542` är kvalitetsgrindens villkor `if canonical_match and trending_feed.get("source") == "static_seed":`. När en agent i stället anropar den tredje annonserade länken `/api/v1/trending/wasted` (eller någon annan scout-endpoint) är `canonical_match` `None`. Anropet passerar då utan `503`-kontroll, tar betalt 0,05 USDC och anropar `fetch_dynamic_asset_pulse` (`app/services/market_data.py:363–424`). Om CoinGecko saknar `coingecko_id` (t.ex. `"wasted-2"`) eller svarar med fel levereras hårdkodade `price_usd: 1.25`, `change_24h_pct: 4.5`, `volume_24h_usd: 12500000.0` med `source_status: "fallback_resilient_feed"`, och `asset`-objektet saknar både `is_stale` och `is_synthetic`. Samma mönster finns i `/api/v1/base-dex-radar` (`app/services/market_data.py:436–468`), som vid 429 levererar tre hårdkodade pooler (`3120.50 / 1.84 / 1.32`) utan Y1:s retry eller last-good-skydd.

**Z2. Partiell DexScreener-träff bäddar tyst in fallback-seed som `is_stale: False` i `_last_good_live` — och `3379eac`:s eget test råkade ut för det (medel/låg).** I `app/services/market_data.py:695–753` sätts `is_live = True` så fort DexScreener returnerar minst ett par. Om svaret innehåller par för `morpho` men saknar par för `virtual` (`chosen_pair is None`), faller koden in i `else:`-grenen på rad 718–723, hämtar `item["fallback"]` (`912 214,33 / 1 058 771,35 / −1,33`), sätter `"is_stale": False` (rad 745) och sparar detta i `_last_good_live["payload"]` (rad 749). I `tests/test_m3_services.py:201` har `_FakeAsyncClient` en 41-teckens adress för `virtual` (`"0x0b3e328455c4059ee9e3f84b5543f74e24e7e1b"`, saknar `b` i `eeb9e` jämfört med `market_data.py:582`). Vid körning av `_FakeAsyncClient` får därför `morpho` testvärdet `900000.0`, medan `virtual` tyst får det statiska seed-värdet `912214.33` med `is_stale: False`, vilket därefter serveras som `dexscreener_base_live_last_good`.

**Z3. `last_good` tillåter betalda realtidsanrop på upp till 6 timmar gammal data, och `503` vid kallstart döljer `402`-schemat för obetalda katalogprober (låg).** `TRENDING_LAST_GOOD_MAX_AGE_SECONDS = 6 * 3600` (`market_data.py:24`) är väl avvägt för det fria `/api/v1/trending`, där `is_stale: true` och `data_age_seconds` deklareras öppet. Men eftersom `api_v1.py:542` bara stoppar `source == "static_seed"` (och inte `is_stale == True` över en snävare maxålder, t.ex. 15–30 min), kan en kund debiteras 0,05 USDC för fem timmar gammal DEX-orderflow under ett längre 429-fönster. Omvänt ligger `503`-kontrollen före `require_x402_payment` även när anropet saknar betalheaders (`X-PAYMENT` / `X-PAYMENT-PROOF`): det skyddar en legacy-agent från att skicka en on-chain-betalning i blindo under `static_seed`, men innebär att en katalogcrawler som bara vill inspektera `402`-prisschemat direkt efter en kallstart + 429 får `503` i stället för `402`.

**Z4. Prune-logiken i `register_dynamic_endpoint` kan radera `morpho` och `virtual` ur `dynamic_endpoints`, och dashboarden dubbelräknar dem (låg).** `_bootstrap_canonical_endpoints` (`app/main.py:43–60`) registrerar `morpho` och `virtual` först vid containerstart, vilket ger dem äldst `created_at`. I `app/database.py:409–413` raderar `register_dynamic_endpoint` alla rader med `calls_count = 0` som inte hör till de 12 nyaste (`ORDER BY created_at DESC LIMIT 12`). När `autopilot_scout_loop` har registrerat 11 nya slugar och `morpho`/`virtual` ännu har `calls_count = 0`, raderas de kanoniska raderna ur tabellen (och försvinner då åter ur `POST /mcp` `list_trending_assets`, `/llms.txt` och `/agents.json`). Dessutom beräknar `app/routers/dashboard.py:343, 351, 542` antalet tjänster som `3 + len(dynamic_endpoints)` och presenterar tabellens rader som *"extra trend-API:er automatiskt"*, där `morpho` och `virtual` nu räknas dubbelt.

### Uppdaterat betyg

| Område | Efter 9 | Efter 10 | Nu (Efter 11) |
| --- | --- | --- | --- |
| Idé och discovery | 8,5 | 8,8 | **8,9** |
| Dataförtroende | 8,2 | 8,0 | **8,4** |
| Betalningsflöde | 7,2 | 7,4 | **7,5** |
| MCP-kompatibilitet | 7,5 | 7,5 | **7,8** |
| Trovärdighet/juridik | 7,3 | 7,5 | **7,8** |
| **Snitt** | **7,7** | **7,8** | **8,1** |

- **Dataförtroende (+0,4 till 8,4):** Y1 och Y2 är nu bevisade i produktion över hela livscykeln (`static_seed` med `503` → `dexscreener_base_live` med `HEALTHY` → `dexscreener_base_live_last_good` med sann ålder i sekunder och `DEGRADED`). Det som hindrar 9,0 är Z1 (att scout-slugar och `/base-dex-radar` fortfarande kan falla tillbaka till statiska tal) samt Z2 (partiell träff).
- **MCP-kompatibilitet (+0,3 till 7,8) & Discovery (+0,1 till 8,9):** Genom `_bootstrap_canonical_endpoints` returnerar `POST /mcp` (`list_trending_assets`), `/llms.txt` och `/agents.json` nu de kanoniska tillgångarna `morpho` och `virtual` tillsammans med scout-tillgångarna.
- **Trovärdighet (+0,3 till 7,8) & Betalningsflöde (+0,1 till 7,5):** Att tjänsten aktivt avstår från att ta betalt (`503 DATA_QUALITY_UNAVAILABLE`) hellre än att sälja statiska seed-värden på kanoniska endpoints är ett stort steg i mognad. Taket på 7,5 för betalningsflödet ligger fast tills en riktig transaktion på Base Mainnet har genomförts (`total_calls_served > 0`).

### Utlåtande och nästa steg

Commit `3379eac` lyfter helhetsbetyget över 8-strecket (**8,1/10**). De två viktigaste arkitekturförbättringarna — att bevara senast verifierade live-observation med sann ålder vid 429 (`Y1`) och att vägra ta betalt för statisk seed-data (`Y2`) — är nu verifierade i faktisk produktionsdrift på `johngarp.click`.

För att stänga de sista tekniska luckorna (Z1–Z4) rekommenderas:
1. **Z1:** Låt `get_dynamic_trending_endpoint` även för icke-kanoniska slugar (och `/api/v1/base-dex-radar`) returnera `503 DATA_QUALITY_UNAVAILABLE` när underliggande källa är i fallback-läge (`source_status != "coingecko_live"` respektive `source_status != "dexscreener_base_live"`), och inkludera `is_stale`/`is_synthetic` konsekvent.
2. **Z2:** I `fetch_trending_dex_tokens` (`app/services/market_data.py:718–745`): om `chosen_pair is None` för en enskild token, hämta den tokenens senast kända värde ur `_last_good_live` med `is_stale: True` (eller markera posten `is_stale: True` om fallback måste användas) — aldrig `is_stale: False` på fallback-data. Rätta även 41-teckensadressen i `tests/test_m3_services.py:201`.
3. **Z4:** Exkludera `CANONICAL_TRENDING_ENDPOINTS` (`morpho`, `virtual`) från `DELETE`-pruningen i `register_dynamic_endpoint` (`WHERE calls_count = 0 AND slug NOT IN ('morpho', 'virtual') ...`).
4. **Riktigt betalbevis:** Genomför ett skarpt köp på Base Mainnet (0,01 eller 0,05 USDC) så att `total_calls_served > 0` kan verifieras live.
## 21. Tolfte uppföljningen (8 november 2026, commit c356e56)

**Underlag och metod.** Diffen `3379eac..c356e56` omfattar 6 filer (+529/−70): `app/database.py`, `app/routers/api_v1.py`, `app/routers/dashboard.py`, `app/services/market_data.py`, `app/services/scout.py` och `tests/test_m3_services.py`. Jag har läst hela diffen, kört sviten själv (**62 passed** på 41,96 s) och gjort egna anrop mot produktionen 16:26–16:34 UTC på instansen `inst_bbba75516af1` (uptime 121–205 s). Därtill tre lokala reproduktioner: CoinGecko direkt för `wasted-2`, `fetch_dynamic_asset_pulse` i både live- och tvingat felläge, samt `fetch_trending_dex_tokens` med partiell träff följd av 429. Slutligen tre betalprober mot produktionen. Samma princip som tidigare: ett påstående räknas först när det syns i koden eller i ett eget svar.

### Status Z1–Z4

| Punkt | Åtgärd i c356e56 | Status | Belägg |
| --- | --- | --- | --- |
| Z1 | 503-grind och last-good även för scout-slugar och `/base-dex-radar` | **Helt löst** | `/trending/morpho` och `/base-dex-radar` ger `503 DATA_QUALITY_UNAVAILABLE` med `source: static_seed` och `fallback_reason: "DexScreener HTTP 429"`; tvingat CoinGecko-fel lokalt ger `static_seed` + `is_synthetic: true`, och `test_z1…` asserts 503 samt `total_calls == 0` |
| Z2 | Partiell träff markeras stale/syntetisk, `_last_good_live` uppdateras bara vid full träff | **Delvis löst** | 41-teckensadressen är rättad, `test_z2…` passerar och en saknad token utan tidigare observation får `is_stale: true` + `is_synthetic: true` utan att `_last_good_live` skrivs. Men blandade träffar nollställer åldern (se AA2) |
| Z3 | `PAID_MAX_STALE_AGE_SECONDS = 900` | **Löst** | Grinden ligger före betalning på alla tre säljvägar; `test_z3…` ger 503 för 3 600 s gammal last_good medan fria flödet fortsatt svarar 200 |
| Z4 | Kanoniska slugar undantas pruningen, korrekt visningsnamn i upsert | **Löst** | `test_z4…` registrerar 15 scout-rader och `morpho`/`virtual` finns kvar; pruningen räknar nu 12 icke-kanoniska rader och `increment_dynamic_endpoint_stats` hämtar namn ur `CANONICAL_TRENDING_ENDPOINTS` |

### Live-observationer

- **`/api/v1/trending`:** `source: static_seed`, `fallback_reason: "DexScreener HTTP 429"`, `data_as_of: null`. `morpho` 521 828,24 / 172 231,95 / −1,27, `virtual` 912 214,33 / 1 058 771,35 / −1,33, `wasted` med `source: autonomous_scout_seed`, `is_synthetic: true` och `data_as_of: null`.
- **`/api/v1/trending/morpho`:** `503` med `retry-after: 60` och `meta.source: static_seed`. **`/api/v1/base-dex-radar`:** `503` på samma sätt. **`?sample=true`:** `200` på alla tre. **Okänd slug:** `404`.
- **Att `/api/v1/trending/wasted` svarar `402` är korrekt och inte en läcka.** Scout-vägen går mot CoinGecko, inte DexScreener. Lokal reproduktion med samma `coingecko_id` ger `source_status: coingecko_live`, `price_usd: 0,02121847`, `change_24h_pct: 44,45`, `volume_24h_usd: 8 086 004,66` och `is_stale: false`; CoinGecko svarar `200` för `wasted-2` även från min adress. Grinden släpper alltså bara igenom när källan faktiskt är live, vilket är precis vad Z1 skulle åstadkomma.
- **Betalprober:** `X-PAYMENT-PROOF: test_tx_round12_probe_001` → `402`, skräpbevis (`0xdeadbeef…`) → `402`, `/api/v1/deep-market-report` utan bevis → `402`. Produktionen kör alltså inte i testläge (`TESTING=false`, `strict_onchain` enligt config-default), och ett `test_tx_`-bevis kan inte användas för att få data gratis. Den sista tekniska misstanken mot betalgrinden är därmed avförd.
- **`/status`:** `dexscreener: DEGRADED`, `total_calls_served: 0`, `persistence_scope` oförändrat efemär.

### Nya fynd (AA = rond 12)

**AA1. Den fria listan visar påhittade siffror för scout-slugarna, och de matchar inte det betalda svaret (medel).** `wasted` listas med `liquidity_usd: 124 850,2`, `volume_24h_usd: 48 900,5`, `momentum_24h_pct: 2,45` och beskrivningen "Live orderflow & sentiment for WASTED". Det är inga observerade värden — posten är märkt `source: autonomous_scout_seed` och `is_synthetic: true` — medan det betalda anropet i dag levererar CoinGecko-spot (0,0212 USDC, +44,45 %, volym 8,09 M). Markeringen är ärlig, men siffrorna ser ut som marknadsdata i discovery, och den som betalar får ett annat datapar än den som bara läser listan.

**AA2. Blandad träff nollställer åldern för gamla värden (medel, kvarvarande Z2).** `newly_observed_tokens` tar med även den token som serveras ur `prior_good_tokens`, så villkoret `len(newly_observed_tokens) == len(tokens_config)` blir sant trots att en token är timmar gammal. Reproducerat lokalt: med `virtual` 2 h gammal och ett DexScreener-svar som bara innehåller `morpho` skrivs `_last_good_live` om med `_fetched_ts = nu` och `data_as_of = nu`, medan `virtual` behåller sina 2 h gamla värden. Vid nästa 429 rapporteras `source: dexscreener_base_live_last_good` med `data_age_seconds: 0` — alltså passerar 900-sekundersgrinden med två timmar gamla tal. Per token sätts `is_stale: true`, men det finns ingen per-token-ålder och feedens egen `is_stale` är `false` i blandläget.

**AA3. `?sample=true` saknar kvalitetsfält (låg).** Schemaförhandsvisningen för `wasted` innehåller varken `is_stale` eller `is_synthetic` i `asset`, medan det betalda svaret gör det. En agent som bygger sin parser på sample-payloaden får ett annat fältset än den betalda modellen. Litet, men samma asymmetri som Y2 anmärkte, nu i sample-lagret.

**AA4. `total_services` räknar in kanoniska rader i "3 +"-formeln (information).** `dashboard.py:346` lämnades orörd (`3 + len(all_dyn)`), medan detaljtexten delades upp i scout respektive kanoniska. Antalet är inte fel om avsikten är säljbara endpoints, men formeln summerar två populationer med samma basfält. Ingen funktionspåverkan.

### Är alla tekniska hinder före ett skarpt mainnet-betalbevis stängda?

Nästan — och det som återstår är avgränsat:

1. **Betalgrinden håller.** Alla tre säljvägar (kanonisk, scout, radar) vägrar seed-data med `503` före betalning, och produktionen accepterar varken `test_tx_`- eller skräpbevis. Det finns ingen väg till gratis data via fejkade bevis, vilket var den enda kvarvarande misstanken mot betalflödet.
2. **Ett hinder är inte stängt: AA2.** Så länge en blandad träff nollställer åldern kan en betalande agent få upp till sex timmar gamla tal för en enskild token trots 15-minutersgrinden. Det hindrar inte att ett betalbevis *genomförs*, men det är skäl att inte sälja under ett längre 429-fönster förrän det är åtgärdat.
3. **Det formella hindret är betalbeviset självt.** `total_calls_served: 0`, ingen settlement-transaktion och ingen BaseScan-länk. Koden och grinden är nu i ett skick där ett skarpt köp på 0,05 USDC bör gå igenom på `/api/v1/trending/wasted` (live i dag) eller 1,00 USDC på `/deep-market-report`.
4. **Beviset måste fångas i rätt fönster.** SQLite är fortfarande efemär, så `total_calls_served` nollställs vid nästa deploy. En BaseScan-länk plus avläsning av `/status` direkt efter köpet är det som gäller; väntar man till efter nästa deploy finns ingen ackumulerad siffra kvar.

### Uppdaterat betyg

| Område | Efter 10 | Efter 11 | Nu (Efter 12) |
| --- | --- | --- | --- |
| Idé och discovery | 8,8 | 8,9 | **9,0** |
| Dataförtroende | 8,0 | 8,4 | **8,6** |
| Betalningsflöde | 7,4 | 7,5 | **7,5** |
| MCP-kompatibilitet | 7,5 | 7,8 | **7,8** |
| Trovärdighet/juridik | 7,5 | 7,8 | **7,9** |
| **Snitt** | **7,8** | **8,1** | **8,2** |

Dataförtroendet går upp 0,2: grinden gäller nu alla tre säljvägar och är bevisad i drift, inte bara i test. Det som håller det under 9 är AA2 och de påhittade scout-siffrorna i AA1. Discovery går upp 0,1 eftersom prune-skyddet gör att de kanoniska länkarna överlever både omstart och femton scoutregistreringar. Betalningsflödet står stilla på 7,5 — ingenting i själva betalningen har ändrats, och taket ligger kvar tills en riktig transaktion finns. Trovärdigheten går upp 0,1 för att avvisandet av testbevis är verifierat och grinden nu är konsekvent mellan endpoints.

### Utlåtande

Rond 12 stänger Z1, Z3 och Z4 samt halva Z2. Det viktigaste är inte de enskilda fixarna utan att kvalitetsgrinden nu är en egenskap hos tjänsten i stället för hos en endpoint: kanoniska slugar, scout-slugar och `/base-dex-radar` vägrar alla att sälja hårdkodade tal, och de vägrar innan någon betalning begärs. Tillsammans med att produktionen avvisar både `test_tx_`-bevis och skräpbevis är betalvägen nu tekniskt trovärdig att prova med riktiga pengar.

Det som återstår är två saker, och bara en av dem är teknisk. AA2 är teknisk och bör åtgärdas före ett längre 429-fönster: en blandad träff får inte nollställa åldern för den token som kommer ur `prior_good`. Den andra är beviset, som ingen kod kan ersätta. Min bedömning är att plattformen är redo för ett skarpt köp nu, i den här ordningen: åtgärda AA2, kör köpet, fånga BaseScan och `/status` i samma fönster, och sätt betalflaggan till skarp först därefter.

### Rekommendationer

**Före skarpt betalbevis (P0)**

1. **AA2:** uppdatera `_last_good_live` bara med de tokens som faktiskt observerades i omgången, och låt `_fetched_ts`/`data_as_of` styras av den äldsta tokenen i payloaden (eller lägg `data_age_seconds` per token). Test: `virtual` 2 h gammal plus endast `morpho` i svaret ska ge `data_age_seconds >= 7200` vid nästa 429, inte 0.
2. **Betalbevis:** 0,05 USDC mot `/api/v1/trending/wasted` eller 1,00 USDC mot `/deep-market-report`, BaseScan-länk, `total_calls_served` avläst före nästa deploy, och ett replay-försök från annan IP som ska avvisas.

**Före bred marknadsföring (P1)**

3. **AA1:** sätt `liquidity_usd`, `volume_24h_usd` och `momentum_24h_pct` till `null` för poster med `is_synthetic: true`, eller visa dem bara när de kommer från en observation.
4. **AA3:** lägg `is_stale` och `is_synthetic` i sample-modellen så att schema och betalt svar är identiska.
5. **Persistent volym:** flytta SQLite till en Render-disk. Utan den kan ingen katalog visa ackumulerad trafik, och varje deploy nollar betalbeviset.
## 22. Trettonde uppföljningen (8 november 2026, commit 839250f)

**Underlag och metod.** Diffen `c356e56..839250f` omfattar 5 filer (+322/−42): `app/routers/api_v1.py`, `app/routers/dashboard.py`, `app/services/market_data.py`, `app/templates/dashboard.html` och `tests/test_m3_services.py`. Jag har läst hela diffen och de tre nya testerna, kört sviten själv (**65 passed** på 46,56 s) och gjort egna anrop mot produktionen 16:48–16:52 UTC på instansen `inst_ae00a50c1b4d` (uptime 229 s). Därtill tre lokala reproduktioner: partiell träff följd av 429 (AA2), kall start utan `last_good` (AA1-residyn) samt cacheträff efter 429. Slutligen en betald kanonisk svarsstruktur i sandlåda för att jämföra nyckelstrukturen med `?sample=true`.

### Status AA1–AA4

| Punkt | Åtgärd i 839250f | Status | Belägg |
| --- | --- | --- | --- |
| AA1 | Syntetiska scout-poster får `null` i liq/vol/momentum/pool_age/klass/dex | **Delvis löst** | Live: `jos` listas med `is_synthetic: true` och samtliga sex fält `null`. Men `static_seed`-grenen i `market_data.py:813–838` är orörd och säljer fortfarande `521 828,24 / 172 231,95 / −1,27` för `morpho` utan `is_synthetic` (se AB1) |
| AA2 | Per-token `_observed_ts`, `data_as_of`, `data_age_seconds`; feednivå från äldsta token; 503 per token | **Löst** | Reproducerat: `virtual` 2 h gammal + färsk `morpho` ger feed-ålder 7 200 s, `virtual` 7 200 s och `morpho` 0 s; nästa 429 behåller 7 199 s, cacheträffen 7 200 s. `test_aa2…` asserts även 503 på betald `virtual` med `total_calls == 0` |
| AA3 | `is_stale`/`is_synthetic` i sample-`asset` och `is_stale`/`fallback_reason` i sample-`meta` | **Löst (flaggor), paritetspåståendet håller inte** | Live: `morpho`, `jos` och `/base-dex-radar` med `?sample=true` innehåller nu flaggorna. Nyckelstrukturen är dock inte identisk med det betalda svaret (se AB2) |
| AA4 | `canonical_count` och `scout_built_count` särskiljs i formel, JSON och mall | **Löst (kodnivå)** | `total_services = 3 + canonical_count + scout_built_count`, `detail` använder nu `canonical_count`, mallen rad 296 använder båda. Kunde inte verifieras live: `/admin` kräver session och `/api/admin/self-check` kräver PIN |

### Live-observationer

- **`/status` (inst_ae00a50c1b4d):** `dexscreener: UNKNOWN`, `coingecko_spot_fallback: STANDBY_BACKUP`, `payai_facilitator: HEALTHY`, `total_calls_served: 0`, persistence fortfarande efemär.
- **`/api/v1/trending`:** 3 poster, `meta.source: dexscreener_base_live_last_good`, `fallback_reason: "DexScreener HTTP 429"`, feed-ålder 191 s. `morpho` 926 575,48 / 212 373,89 / −1,01 (DEEP_LIQUIDITY), `virtual` 883 478,31 / 1 009 153,37 / −1,07, båda `is_stale: true` med egen `data_as_of` och `data_age_seconds: 191`. `jos` (Be Like José) med `is_synthetic: true` och alla mätvärden `null`.
- **Betalda endpoints:** `/api/v1/trending/morpho` → `402`, `/api/v1/trending/jos` → `402`. Båda passerar alltså grinden med 191 s gammal data, vilket är korrekt (< 900 s).
- **Sample:** `/trending/morpho?sample=true`, `/trending/jos?sample=true` och `/base-dex-radar?sample=true` svarar `200` med flaggor i både `asset` och `meta`.
- **`/` (dashboard):** `200`. **`/admin`:** `200` men renderar inloggningsformuläret utan session, så räknaren går inte att läsa ut live utan PIN.

### Nya fynd (AB = rond 13)

**AB1. `static_seed`-grenen är orörd och visar fabricerade tal utan att märka dem som syntetiska (medel).** Reproducerat vid kall start med 429 och tom `_last_good_live`: `morpho` listas med `liquidity_usd: 521 828,24`, `volume_24h_usd: 172 231,95`, `momentum_24h_pct: −1,27`, `liquidity_class: DEEP_LIQUIDITY`, `dex: "Aerodrome / Base"`, `is_stale: true`, `data_as_of: null` — men **ingen `is_synthetic`-nyckel**. `virtual` på samma sätt med `912 214,33 / 1 058 771,35 / −1,33`. AA1 städade scout-grenen och "aldrig observerad"-grenen, men inte den tredje vägen, som är precis den som används vid kall start och efter sex timmar utan DexScreener. Den som läser discovery får alltså fortfarande påhittade djup- och volymtal som ser ut som marknadsdata, utan den flagga som skulle avslöja dem.

**AB2. Sample och betalt svar har fortfarande olika nycklar (låg–medel).** Sample-`asset`: `change_24h_pct`, `coingecko_id`, `momentum_signal`, `name`, `price_usd`, `slug`, `symbol`, `volume_24h_usd`, `is_stale`, `is_synthetic`. Betald kanonisk `asset`: `liquidity_usd`, `volume_24h_usd`, `momentum_24h_pct`, `dex`, `liquidity_class`, `pool_age_days`, `name`, `slug`, `symbol`, `is_stale`, `is_synthetic`. `price_usd` och `change_24h_pct` finns alltså bara i sample, medan `liquidity_usd`, `momentum_24h_pct`, `dex`, `liquidity_class` och `pool_age_days` bara finns i det betalda svaret. Även `meta` skiljer sig: sample har `sources` och `status`, det betalda svaret har `source`. AA3 levererade flaggorna, men sample går fortfarande inte att använda som kontrakt för parsern.

**AB3. Syntetiska poster beskrivs fortfarande som "Live orderflow" (låg).** `jos` har `description: "Live orderflow & sentiment for Be Like José (JOSÉ)"` medan alla mätvärden är `null` och `data_as_of: null`. Texten motsäger flaggan.

**AB4. Sex-timmarsfönstret är nu kopplat till den äldsta tokenen (låg, designavvägning).** Eftersom `_last_good_live["_fetched_ts"]` sätts till äldsta tokenens observation, faller hela feeden till `static_seed` när en enskild token varit onåbar i sex timmar — även om den andra tokenen är färsk. En avlistad eller permanent saknad token släcker därmed båda kanoniska betalendpoints i stället för bara den egna. Fail-closed är försvarbart, men det är en tillgänglighetsregression jämfört med per-token-semantiken som AA2 införde.

**AB5. Dashboardräknaren är oförändrad i sak (information).** `3 + canonical_count + scout_built_count` ger samma summa som tidigare `3 + len(all_dyn)`; ändringen är en uppdelning av etiketterna, inte en korrigering av antalet. Det stämmer med att AA4 klassades som information i rond 12, men det innebär att inget faktiskt mätfel åtgärdades — det fanns heller inget att åtgärda.

### Är hindren före ett skarpt mainnet-betalbevis nu stängda?

**Ja, det sista tekniska hindret är stängt.** AA2 var det enda jag höll öppet i rond 12, och det är nu åtgärdat i både datalagret och grinden: varje token bär sin egen ålder, feednivån speglar den äldsta, och ett betalt anrop på en token äldre än 900 s nekas med 503 före betalning. Jag har reproducerat båda leden (2 h gammal token → 7 200 s → grind) och cacheträffen förvränger inte åldern.

Kvar är endast beviset: `total_calls_served: 0`, ingen settlement-transaktion, ingen BaseScan-länk. AB1, AB2 och AB3 är kvalitetsbrister i det fria flödet och i schemadokumentationen — de påverkar inte betalgrinden, eftersom `static_seed` aldrig säljs. De bör åtgärdas före bred marknadsföring, inte före köpet.

### Uppdaterat betyg

| Område | Efter 11 | Efter 12 | Nu (Efter 13) |
| --- | --- | --- | --- |
| Idé och discovery | 8,9 | 9,0 | **9,0** |
| Dataförtroende | 8,4 | 8,6 | **8,7** |
| Betalningsflöde | 7,5 | 7,5 | **7,5** |
| MCP-kompatibilitet | 7,8 | 7,8 | **7,8** |
| Trovärdighet/juridik | 7,8 | 7,9 | **8,0** |
| **Snitt** | **8,1** | **8,2** | **8,2** |

Dataförtroendet går upp 0,1: per-token-ålder och den skärpta grinden är den viktigaste enskilda förbättringen sedan Z1, och den är verifierad i både kod, test och reproduktion. Att det inte blir mer beror på AB1 — discovery visar fortfarande påhittade tal vid kall start. Trovärdigheten går upp 0,1 för att alla fyra punkterna är åtgärdade med tester i samma rond. Betalningsflödet står kvar på 7,5: inget i betalningen har ändrats, och betyget kan inte stiga förrän en riktig transaktion finns. Snittet ligger kvar på 8,2 eftersom uppgångarna vägs upp av att betalningsdelen står stilla.

### Utlåtande

Rond 13 gör det som rond 12 bad om, och AA2 är ordentligt gjort: åldern flyttas från feeden till token, grinden läser tokenens egen ålder, och både partiell träff och cacheträff beter sig rätt. Det var den sista tekniska invändningen mot att ta betalt, och den är borta.

Det som återstår är av två slag. Det ena är betalbeviset, som är ett faktum om verksamheten och inte om koden. Det andra är att samma princip som AA1 införde för scout-poster inte har förts hela vägen: `static_seed`-grenen visar fortfarande hårdkodade djup- och volymtal, och den är den väg som används vid kall start och efter sex timmar utan DexScreener. Så länge den finns kvar finns det en yta där påhittade tal presenteras som marknadsdata — inte säljbara, men synliga.

Min rekommendation är därför oförändrad i ordning: genomför betalbeviset nu, fånga BaseScan och `/status` i samma fönster före nästa deploy, och ta AB1–AB3 i nästa rond innan katalogerna får skarp betalflagga.

### Rekommendationer

**Före skarpt betalbevis (P0)**

1. **Betalbevis:** 0,05 USDC mot `/api/v1/trending/wasted` (CoinGecko-live i dag) eller 1,00 USDC mot `/deep-market-report`. Fånga BaseScan-länken och läs av `total_calls_served` före nästa deploy, samt försök replay från annan IP som ska avvisas.

**Före bred marknadsföring (P1)**

2. **AB1:** sätt `is_synthetic: true` och nolla `liquidity_usd`, `volume_24h_usd`, `momentum_24h_pct`, `pool_age_days`, `liquidity_class` och `dex` även i `static_seed`-grenen. Samma princip som AA1, tredje vägen.
3. **AB2:** låt sample-modellen spegla det betalda svaret (eller dokumentera skillnaden explicit i `sample_notice`), så att en agent kan bygga sin parser på `?sample=true`.
4. **AB3:** låt `description` följa källan — "Live orderflow" bara när posten är observerad.
5. **AB4:** överväg att låta sex-timmarsfönstret vara per token även vid serve, så att en död token inte släcker den andra.
6. **Persistent volym:** flytta SQLite till en Render-disk, annars nollställs betalbeviset vid varje deploy.
## 23. Fjortonde uppföljningen (8 november 2026, commit 02b8cf1)

**Underlag och metod.** Diffen `839250f..02b8cf1` omfattar 6 filer (+187/−41): `app/database.py`, `app/main.py`, `app/routers/api_v1.py`, `app/routers/dashboard.py`, `app/services/market_data.py` och `tests/test_m3_services.py`. Jag har läst hela diffen och de tre nya testerna, kört sviten själv (**68 passed** på 23,28 s) och gjort egna anrop mot produktionen 17:06–17:14 UTC på instansen `inst_dc425f7e5167` (uptime 172 s). Därtill fyra lokala verifieringar i sandlåda: nyckeljämförelse sample mot betalt svar för kanonisk slug, scout-slug och radar, samt mätning av betaltelemetrin före och efter tre anrop.

### Status AB1–AB3 och telemetrin

| Punkt | Åtgärd i 02b8cf1 | Status | Belägg |
| --- | --- | --- | --- |
| AB1 | `static_seed`-grenen nollar mätvärdena och sätter `is_synthetic: True` | **Löst** | Live: `morpho` och `virtual` listas med `is_synthetic: true`, `is_stale: true` och `liquidity_usd`, `volume_24h_usd`, `momentum_24h_pct`, `pool_age_days`, `liquidity_class`, `dex` alla `null`. Inga fabricerade tal kvar i discovery |
| AB2 | Kanonisk sample speglar DEX-schemat, scout-sample speglar CoinGecko-schemat | **Löst för kanonisk och radar, nästan för scout** | Kanonisk: `asset` 11/11 nycklar identiska, `meta` 6/6, samma `tier`. Radar: `meta` 7/7 och pool 10/10 identiska. Scout: `asset` 10/10, men sample har en extra `source`-nyckel i `meta` (se AC2) |
| AB3 | Beskrivningen för syntetiska poster är sanningsenlig | **Löst** | Live: `jos` har `description: "Trending asset profile for Be Like José (JOSÉ) - orderflow feed pending live market trade"` |
| Telemetri | Nekade betalningsförsök loggas som `PAYMENT_REJECTED` | **Löst** | Sandlåda: anrop utan bevis gav `quotes_402: 0 → 1`; två anrop med bevisheader gav `payment_rejected_hits: 1 → 3`. Brickan `⚠️ BETALNING NEKAD` finns i `dashboard.py` och CSS-klassen `b-block` i mallen |

### Live-observationer

- **`/status` (inst_dc425f7e5167):** `dexscreener: UNKNOWN`, `coingecko_spot_fallback: STANDBY_BACKUP`, `payai_facilitator: HEALTHY`, `total_calls_served: 0`, persistence fortfarande efemär.
- **`/api/v1/trending`:** `meta.source: static_seed`, `fallback_reason: "DexScreener HTTP 429"`, `data_as_of: null`, `data_age_seconds: null`. Alla tre posterna har `null` i samtliga mätvärden; `morpho` och `virtual` med `is_synthetic: true` och `is_stale: true`, `jos` med `source: autonomous_scout_seed` och den nya beskrivningen.
- **Betalda endpoints:** `/trending/morpho` → `503 DATA_QUALITY_UNAVAILABLE` (korrekt, feeden är static_seed), `/trending/jos` → `402` (CoinGecko-vägen är live), `/trending/wasted` → `404` (se AC3).
- **`/trending/morpho?sample=true`:** `asset` med 11 nycklar och `meta` med 6 nycklar, `tier: dynamic_trending_0.05_usdc` — identiskt med det betalda svaret i sandlåda. **`/trending/jos?sample=true`:** scout-schema, `tier: dynamic_scout_0.05_usdc`. **`/base-dex-radar?sample=true`:** 10 poolnycklar, 7 metanycklar, identiskt med betalt svar.

### Nya fynd (AC = rond 14)

**AC1. `_observed_ts` läcker i betalda svar för scout och radar (låg).** `fetch_dynamic_asset_pulse` och `fetch_base_dex_radar` lägger `_observed_ts` på toppnivå i payloaden, och båda rutterna returnerar payloaden oförändrad. I sandlåda har det betalda scout-svaret toppnycklarna `_observed_ts, asset, cache_hit, meta, source_status, tier, timestamp` och radar-svaret `_observed_ts, cache_hit, meta, network, source_status, summary, tier, timestamp, top_base_pools`. Den fria listan och det betalda kanoniska svaret strippar fältet, så det är inkonsekvent och läcker intern bokföring till betalande kunder. Ingen funktionspåverkan, men det bör bort innan externa agenter börjar spara svaren.

**AC2. Scout-sample har en extra `meta.source` som det betalda scout-svaret saknar (låg).** Betald scout-`meta`: `as_of`, `data_age_seconds`, `disclaimer`, `fallback_reason`, `is_stale`, `sources`, `status`. Sample har samma sju plus `source`. `asset` är däremot identisk (10/10). Pariteten som efterfrågades är alltså uppnådd i sak, men sample är fortfarande en aning vidlyftigare än kontraktet.

**AC3. Scout-slugar är inte varaktiga, och en tidigare annonserad betalendpoint svarar nu 404 (medel).** `/api/v1/trending/wasted` gav `402` på instans `inst_bbba75516af1` i rond 12 och `404` på `inst_dc425f7e5167` i dag, eftersom scout-registreringarna bor i den efemära SQLite-filen och bara `morpho`/`virtual` seedas vid start. En katalog som indexerat en scout-slug får alltså 404 efter varje deploy. Det är samma rotorsak som jag påpekat sedan rond 4, men det här är första gången symptomet syns i en endpoint som redan annonserats som säljbar.

**AC4. `PAYMENT_REJECTED` räknar även rena prober (låg, tolkningsfråga).** Kategoriseringen bygger enbart på att `X-PAYMENT-PROOF`, `X-PAYMENT` eller `PAYMENT-SIGNATURE` finns, inte på att beviset är ett seriöst försök. En skanner som skickar `0xjunk` hamnar i samma hink som en klient med felaktigt belopp. För larmet "betalning nekas" är det acceptabelt, men siffran bör läsas som "försök med header", inte som "misslyckade betalningar".

**AC5. Min egen 402 på radarn var inget fel (notering om metod).** Första radarproben med `test_tx_v14` gav `402` medan trending accepterade samma bevis. Orsaken är att gränsen i `x402.py` är `len(proof) < 12` och `test_tx_v14` är 11 tecken. Med `test_tx_v14_radar_probe_0001` blev svaret `200`. Det var alltså mitt testbevis som var för kort, inte en asymmetri i betalgrinden.

**AC6. Sex-timmarsfönstret är fortfarande kopplat till den äldsta tokenen (låg, kvar från AB4).** Oförändrat sedan rond 13: en enskild token som inte går att observera släcker båda kanoniska endpoints efter sex timmar. Ingen åtgärd utlovad, men den bör finnas med i backloggen.

### Vad rond 14 betyder

Alla tre anmärkningarna är åtgärdade, och för första gången är den fria listan helt fri från påhittade tal: `static_seed`-posterna är nollställda och märkta syntetiska, scout-posterna likaså, och de fasta siffrorna i `fallback`-konfigurationen används inte längre i något publikt svar. Schemapariteteten är dessutom verifierad nyckel för nyckel, inte bara påstådd — kanonisk 11/11 och 6/6, radar 10/10 och 7/7, scout 10/10 i `asset`.

Baksidan är att den ärliga listan nu är tom på siffror i produktion, eftersom DexScreener svarar 429 mot Render-instansens IP. Det är rätt beteende och samtidigt ett produktproblem: discovery visar tre profiler utan ett enda mätvärde. Det gör DexScreener-åtkomsten till nästa riktiga fråga, inte schemat.

### Uppdaterat betyg

| Område | Efter 12 | Efter 13 | Nu (Efter 14) |
| --- | --- | --- | --- |
| Idé och discovery | 9,0 | 9,0 | **9,0** |
| Dataförtroende | 8,6 | 8,7 | **8,9** |
| Betalningsflöde | 7,5 | 7,5 | **7,5** |
| MCP-kompatibilitet | 7,8 | 7,8 | **7,9** |
| Trovärdighet/juridik | 7,9 | 8,0 | **8,1** |
| **Snitt** | **8,2** | **8,2** | **8,3** |

Dataförtroendet går upp 0,2: samtliga fyra vägar (kanonisk live, kanonisk seed, scout, radar) är nu antingen ärliga eller blockerade, och schemapariteten är mätbar. Det som håller det under 9 är AC1 och AC3. MCP går upp 0,1 eftersom sample nu fungerar som parserkontrakt för kanoniska slugar och radar. Trovärdigheten går upp 0,1 för den nya betaltelemetrin. Betalningsflödet står kvar på 7,5 — telemetri är inte en betalning, och `total_calls_served` är fortfarande 0.

### Utlåtande

Rond 14 stänger AB1–AB3 och gör det utan att lämna kvar någon av de tre vägar jag pekade på. Den viktigaste effekten är att ingen endpoint längre kan visa en påhittad siffra: antingen finns en observation med tidsstämpel, eller så är fältet `null` och posten märkt syntetisk. Det är den princip jag efterlyst sedan rond 10, och den håller nu hela vägen.

Kvar finns tre saker, varav ingen är ett hinder för betalbeviset. AC1 och AC2 är städning i svarsformatet. AC3 är den som bör prioriteras: betalendpoints som annonserats utomlands försvinner vid varje deploy, och det är precis den typen av 404 som får en katalog att sluta lita på utbudet. Roten är den efemära databasen, och den åtgärdas bara med persistent volym.

Min rekommendation är oförändrad: genomför betalbeviset nu och fånga BaseScan och `/status` i samma fönster, ta AC1–AC3 i nästa rond, och lös DexScreener-åtkomsten innan discovery marknadsförs igen.

### Rekommendationer

**Före skarpt betalbevis (P0)**

1. **Betalbevis:** 0,05 USDC mot `/api/v1/trending/jos` (CoinGecko-live i dag) eller 1,00 USDC mot `/deep-market-report`. Fånga BaseScan-länk och `total_calls_served` före nästa deploy, samt replay-försök från annan IP som ska avvisas.

**Före bred marknadsföring (P1)**

2. **AC3:** persistent volym (Render-disk) så att scout-slugar och `total_calls_served` överlever deploy. Alternativt: registrera om senast annonserade scout-slugar vid start.
3. **AC1:** strippa `_observed_ts` i `get_dynamic_trending_endpoint` och `get_base_dex_radar`, som redan görs i den fria listan.
4. **AC2:** ta bort `source` ur scout-sample eller lägg till det i det betalda scout-svaret, så att nyckeluppsättningen är symmetrisk.
5. **AC6:** låt sex-timmarsfönstret vara per token även vid serve.
6. **DexScreener:** begär API-nyckel eller byt primärkälla, annars visar discovery alltid `null` från Render-IP:n.
## 24. Femtonde uppföljningen (8 november 2026, commit 8b56b0a)

**Underlag och metod.** Diffen `02b8cf1..8b56b0a` omfattar 3 filer (+71/−7): `app/main.py`, `app/routers/api_v1.py` och `tests/test_m3_services.py`. Jag har läst hela diffen, kört sviten själv (**71 passed** på 51,49 s) och gjort egna anrop mot produktionen 17:24–17:30 UTC på instansen `inst_5bfb2d9a9789` (uptime 260 s). Därtill två lokala verifieringar i sandlåda: de fyra betalda rutternas toppnycklar (`trending/wasted`, `base-dex-radar`, `crypto-pulse`, `deep-market-report`) samt scout-sample mot betalt scoutsvar nyckel för nyckel, med appens lifespan startad så att bootstrap faktiskt körs.

### Status AC1–AC3

| Punkt | Åtgärd i 8b56b0a | Status | Belägg |
| --- | --- | --- | --- |
| AC1 | `_observed_ts` strippas före retur i radar- och scout-rutten | **Löst** | Sandlåda: inga interna fält i något av de fyra betalda svaren. `trending/wasted` toppnycklar `asset, cache_hit, meta, source_status, tier, timestamp`; radar `cache_hit, meta, network, source_status, summary, tier, timestamp, top_base_pools`; `crypto-pulse` och `deep-market-report` likaså utan `_`-fält |
| AC2 | `source` borttagen ur scout-samplens `meta` | **Löst** | Sandlåda: scout-sample `asset` 10 nycklar och `meta` 7 nycklar, identiska med det betalda svaret. Kanonisk (11/11, 6/6) och radar (10/10, 7/7) var redan verifierade i rond 14 |
| AC3 | `wasted` registreras i bootstrapen vid uppstart | **Delvis löst** | Live: `/trending/wasted` → `503` och `/trending/wasted?sample=true` → `200`, alltså ingen 404. Men bootstrapen innehåller exakt en hårdkodad slug (se AD1) |

### Live-observationer

- **`/status` (inst_5bfb2d9a9789):** `dexscreener: UNKNOWN`, `payai_facilitator: HEALTHY`, `total_calls_served: 0`, persistence fortfarande efemär.
- **`/api/v1/trending`:** fyra poster, `meta.source: static_seed`, `fallback_reason: "DexScreener HTTP 429"`. `morpho` och `virtual` med `is_synthetic: true`, `is_stale: true` och alla mätvärden `null`; `jos` och `wasted` med `is_synthetic: true` och `null` i samtliga fält, `data_age_seconds: null`.
- **`/trending/wasted`:** `503 DATA_QUALITY_UNAVAILABLE` — kvalitetsgrinden håller, och 404:n från rond 14 är borta. **`?sample=true`:** `200`.
- **Sandlåda, betalda svar:** samtliga fyra returnerar `200` med testbevis och innehåller inga interna `_`-fält. `deep-market-report` kräver unikt bevis per anrop, annars slår replay-skyddet till — det är korrekt.

### Nya fynd (AD = rond 15)

**AD1. AC3 är en hårdkodad enstaka slug, inte en mekanism (medel).** `_bootstrap_canonical_endpoints` lägger till exakt en post: `wasted`, med `coingecko_id: "wasted-2"` och `price_usdc: 0.05` skrivet direkt i `main.py`. Alla andra scout-slugar är fortfarande beroende av att scoutern råkade registrera dem i den aktuella instansen. `jos` syns i dagens lista och svarar `402` i sandlåda, men det beror på att CoinGecko-trending råkade innehålla den vid start — nästa deploy med en annan trending-lista ger 404 igen, precis som `wasted` gjorde i rond 14. Den som indexerar `/trending/jos` har alltså fortfarande en bruten länk efter nästa deploy, trots att åtgärden presenterades som "persistent bootstrap av annonserade scout-slugar".

**AD2. Pruningen skyddar bara `morpho` och `virtual`, inte bootstrapade slugar (låg).** `DELETE`-satsen i `register_dynamic_endpoint` undantar enbart de två kanoniska sluggarna. En bootstrapad slug har `calls_count = 0` tills någon betalar, så om tolv nyare scout-slugar registreras under samma instans kan `wasted` prunas i drift — den återkommer först vid nästa omstart. Bootstrapen ger alltså en garanti vid start, inte en varaktig garanti.

**AD3. Tillgångsdefinitionen dupliceras i koden (låg).** `coingecko_id` och pris för `wasted` finns nu på två ställen: i bootstrap-listan och i den databasrad som `register_dynamic_endpoint` skriver. `INSERT OR IGNORE` innebär att den befintliga raden vinner, så en prisändring i `main.py` slår inte igenom på en databas som redan har raden. Det är ofarligt i dag men en uppenbar driftfälla när priserna ska justeras.

**AD4. Bootstrapen nollställer inte statistiken (notering, inget fel).** `INSERT OR IGNORE` lämnar `calls_count` och `revenue_usdc` orörda vid omstart, vilket jag kontrollerade särskilt eftersom en återregistrering annars skulle radera betalbeviset. Så är inte fallet.

**AD5. Metodnotering: min första sandlådekörning gav 404 för `wasted` (inget fel i koden).** `TestClient(create_app(...))` utan context manager startar inte lifespan, och då kör bootstrapen inte. Med `with TestClient(...)` blev svaret `402`. 404:n var alltså min testharnesks artefakt, inte en regression.

### Vad rond 15 betyder

AC1 och AC2 är stängda och verifierade i alla fyra betalda svar, inte bara i de två som ändrades. Det betyder att svarskontraktet nu är rent: inga interna fält, och sample är en trovärdig kopia av det betalda schemat för kanonisk slug, scout-slug och radar. Det är den sista pusselbiten i det som går att verifiera utan en riktig betalning.

AC3 löser symptomet för `wasted` men inte problemet. Så länge sluggen är hårdkodad i `main.py` gäller garantin en tillgång, inte utbudet, och pruningen kan dessutom ta bort den i drift. Det är en ärlig halvåtgärd snarare än en felaktig sådan, men den bör inte beskrivas som att kataloglänkar nu är varaktiga.

### Uppdaterat betyg

| Område | Efter 13 | Efter 14 | Nu (Efter 15) |
| --- | --- | --- | --- |
| Idé och discovery | 9,0 | 9,0 | **9,0** |
| Dataförtroende | 8,7 | 8,9 | **9,0** |
| Betalningsflöde | 7,5 | 7,5 | **7,5** |
| MCP-kompatibilitet | 7,8 | 7,9 | **8,0** |
| Trovärdighet/juridik | 8,0 | 8,1 | **8,2** |
| **Snitt** | **8,2** | **8,3** | **8,3** |

Dataförtroendet når 9,0: alla betalda svar är fria från internfält, alla scheman är symmetriska och ingen endpoint kan visa en påhittad siffra. MCP går upp 0,1 eftersom sample nu är ett komplett kontrakt även för scout-slugar. Trovärdigheten går upp 0,1 för att åtgärderna denna gång verifierades i alla fyra rutterna. Betalningsflödet står kvar på 7,5 — fortfarande ingen transaktion.

### Utlåtande

Rond 15 stänger de två sista formella bristerna i svarsformatet. Det finns nu ingenting kvar i det publika kontraktet som jag kan anmärka på utan att upprepa mig: inga läckta internfält, identiska nyckeluppsättningar mellan sample och betalt svar i alla tre produktfamiljer, och en grind som vägrar sälja data den inte kan belägga.

Kvar är två saker av olika karaktär. Den ena är betalbeviset, som fortfarande är det enda som skiljer plattformen från att vara en fungerande betaltjänst i drift. Den andra är varaktigheten: `wasted` är hårdkodad, `jos` är tillfällig, och pruningen kan ta bort den förstnämnda. Det påverkar inte betalningen av ett enskilt anrop, men det påverkar varje katalog som listar utbudet.

Min rekommendation är nu ännu mer entydig än tidigare: kör betalbeviset, för det finns inget tekniskt hinder kvar i den vägen.

### Rekommendationer

**Före skarpt betalbevis (P0)**

1. **Betalbevis:** 0,05 USDC mot `/api/v1/trending/morpho` eller `/trending/wasted` när kvalitetsgrinden släpper igenom, alternativt 1,00 USDC mot `/deep-market-report`. Fånga BaseScan-länk och `total_calls_served` före nästa deploy, samt replay-försök från annan IP som ska avvisas.

**Före bred marknadsföring (P1)**

2. **AD1:** ersätt den hårdkodade `wasted`-posten med en lista över annonserade slugar (config eller tabell) som bootstrapen läser, så att garantin gäller utbudet och inte en tillgång.
3. **AD2:** lägg de bootstrapade sluggarna i `NOT IN`-listan i pruningen, eller skydda rader med `announced = 1`.
4. **AD3:** låt databasraden vara enda källan för `coingecko_id` och pris, eller gör upserten till en `ON CONFLICT DO UPDATE` för de fält som ska kunna ändras.
5. **Persistent volym:** flytta SQLite till en Render-disk, annars nollställs både utbudet och `total_calls_served` vid varje deploy.
6. **DexScreener:** begär API-nyckel eller byt primärkälla, annars visar discovery alltid `null` från Render-IP:n.
