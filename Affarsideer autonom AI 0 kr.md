# Autonoma AI-affärsidéer med 0 kr i startkostnad

*Deep research 9 november 2026. Underlag: egen läsning av AIM Networks kodbas och drift (commit 8b56b0a), live-anrop mot johngarp.click, samt externa mätningar av x402, Apify, MCP, Virtuals, bountymarknader, trading-agenter och gratisnivåer. Alla tredjepartssiffror är ögonblicksbilder med källa; de är inte garantier.*

---

## 0. Sammanfattning — det obekväma först

1. **Målet $1M/år med 0 kr kapital och full autonomi har ingen belagd precedent 2026.** Det bästa dokumenterade utfallet för en enskild autonom säljare ligger på **$470/månad i snitt** (Apify:s 3 000–4 500 utvecklare delar $1,4–1,6M/månad), med en topp på **$10 000+/månad** för de allra bästa. x402:s medianförsäljare tjänar **$0.01/månad**.
2. **$500k under år ett är möjligt — men bara vid hög biljett.** 10 kunder à $4 200/månad eller 20 à $2 100. Det finns bevis: `api.surplusintelligence.ai` tog $170k på 30 dagar från **31 betalare** (~$5 500 per betalare), och `agentapi.rozo.ai` $77k från **3 betalare** (~$25 700 per betalare). Den vägen kräver försäljning och trovärdighet, inte mer autonomi.
3. **Mikrobetalning är distribution, inte affärsmodell.** Av 14 502 listningar i Coinbase Bazaar omsatte hela populationen ~$10 300 på 30 dagar; **11 stycken** klarade $100. 93 % tjänade under $1/månad.
4. **Inferens till mikroprix är strukturellt förlustbringande.** Cloudflare Workers AI kostar $0.011 per 1 000 neurons över gratisnivån. En endpoint som säljs för $0.01 och gör ett litet LLM-anrop per request går back. Det som fungerar är **cachad, deterministisk data** — inte genererad text.
5. **Rekommendation:** bygg en barbell — en datamaskin som ger kassaflöde ($500–5 000/mån), en smal B2B-dataproduct som är den enda realistiska $500k-vägen, och en distributionstillgång som persona/kanal. Avstå från bounties, audit-tävlingar och trading som plan: de är lotterier eller kapitalbundna, och reglerna utesluter allt oftare AI.

**Varför AIM Network är rätt jämförelse:** det byggdes för ~0 kr (Render free, gratis RPC, ingen betald data), driftas autonomt av en scout-loop och ett självcheck-system, och säljer via x402 i USDC på Base. AIM bevisar att **produktionen** kan vara gratis och autonom. Det AIM inte bevisar — och ingen annan heller — är att **efterfrågan** blir det.

---

## 1. Tre krav som kolliderar

| Krav | Vad det betyder tekniskt | Vad det betyder ekonomiskt |
|---|---|---|
| **0 kr i utveckling och igångsättning** | Gratisnivåer räcker för kod, hosting, DB, cron och lite inferens | Ingen buffert för marknadsföring, data eller misslyckanden |
| **Helt autonomt, helt online** | Ingen människa i loopen för drift, support eller leverans | Ingen som ringer kunder, förhandlar eller bygger förtroende |
| **$1M/år, $500k år ett** | Kräver antingen enorm volym eller hög biljett | Kräver antingen distribution eller försäljning — båda är mänskliga tillstånd |

Poängen: de två första kraven är uppfyllda av AIM redan i dag. Det tredje kravet är av en annan art. Autonomi automatiserar **leverans**, aldrig **efterfrågan**. Varje idé nedan bedöms därför på hur den skaffar efterfrågan utan människa — och det är där de fallerar eller lyckas.

---

## 2. Vad marknaden faktiskt betalar 2026

| Mätning | Siffra | Källa |
|---|---|---|
| x402, organiska säljare (okt 2026) | 91 säljare, $793k organisk volym/30 d, topp 10 = 76 %, median **$0.01** | x402stats.io/reports/2026-10 |
| x402, alla plånböcker som fick något | 37 495 — 91 klarar organisk-tröskeln | samma |
| Coinbase Bazaar, 14 502 listningar | ~$10 309 till säljare/30 d; **11** över $100; median **$0.03**; 93 % under $1 | circadian-agent.com/research/x402-market |
| Bazaar, betalda anrop | 233k anrop/30 d, ~$17.4k intäkt; krypto-data 356k anrop men bara $7 385 | x402.cp0x.com (2026-10-21) |
| Topp-säljare på x402 (30 d) | Bitrefill $573k · surplusintelligence $170k (31 betalare) · swarmx $90k · rozo $77k (3 betalare) · vapinetwork $68k (24) · dtelecom $36k (34) | x402-trust.com/trust/report |
| x402 totalt (mätt annorlunda) | $197 149 över 523 tjänster, varav **86 % en enda** (BlockRun, $170 244); 66 tjänster över $10 | fiatdock.com/monetize-mcp-server |
| Apify Store | $1,4–1,6M/månad till ~3 000–4 500 utvecklare (snitt ~$470); bland de 900 mest använda aktörerna: median **$14/mån**, 175 > $100, 35 > $1 000 | dev.to (900 actors), apify.com/partners |
| MCP | 37 619 servrar i registret; < 5 % har lyckats monetarisera; kataloger betalar $0 | arte.itlibra.com, mcp-marketplace.io |
| Crypto AI, 130 projekt | $8.7M/månad utanför OpenRouter, varav $7.2M hos Venice; **pay-per-call-gateways ~$3 800/30 d** | BlockBooster via HTX (2026-10-21) |
| Venice via x402 | $3 100 av $7.2M kortförsäljning = **0.05 %** | samma |
| Virtuals ACP | Plattformsavgift $345 197 (mars 2026) → **$5.48** (september); 2 470 agenter har någonsin haft ett jobb; 151 har tjänat > $1 000 | chainward.ai |
| Agent-bounties | 24 finansierade bounties värda **$771**; 161 bidrag för ett $2-pris | agent-bounty-feed, moltstack |
| Audit-tävlingar | 83 % färre tävlingar 2024→2026, 24 % fler bidrag; Immunefi förbjuder AI-genererade rapporter; Code4rena kör egen AI-revisor | munimtechnologies, dev.to |
| LLM-trading | Kalshi −16 % till −30,8 %, Polymarket −1,1 % i snitt; 43,1 % av modell-säsonger lönsamma; 3 av 22 i vinst | theagenttimes, traderank.ai |
| Betalda kanaler | Typisk kanal $500–3 000 MRR; toppnisch $20k–100k; churn 8–15 % | easy-post.app |
| Crypto-nyhetsbrev | Topp: ~30k prenumeranter → $430k–810k/år | substats.io |

**Läsningen:** pengarna finns, men de går till **företag med en produkt och en säljfunktion**, inte till autonoma mikro-agenter. x402 är en betalräls som etablerade bolag lagt till; de 91 organiska säljarna delar en marknad mindre än en enda medelstor SaaS.

---

## 3. Den hårda aritmetiken

$1M/år = $83 300/månad. $500k år ett = $41 700/månad.

| Modell | Pris | Kunder/anrop för $500k/år | För $1M/år |
|---|---|---|---|
| Mikro-API | $0.01/anrop | 4,17M anrop/mån (139k/dag) | 8,3M/mån (278k/dag) |
| Mikro-API | $0.05/anrop | 834k anrop/mån (28k/dag) | 1,67M/mån |
| Premium-API | $0.25/anrop | 167k anrop/mån | 333k/mån |
| B2B-data | $2 100/mån | 20 kunder | 40 kunder |
| B2B-data | $5 500/mån | 8 kunder | 15 kunder |
| B2B-data | $25 000/mån | 2 kunder | 4 kunder |
| Konsument-abonnemang | $60/mån | 695 prenumeranter | 1 389 |
| Konsument-abonnemang | $99/mån | 421 prenumeranter | 842 |
| Annonser | $10 RPM | 50M sidvisningar/år | 100M |
| Trading | 20 %/år | $2.5M kapital | $5M kapital |

Två saker framgår. För det första: **mikro-API-vägen kräver mer trafik än hela x402-ekosystemet har i dag** (233k betalda anrop/30 dagar i Bazaar). För det andra: **hög biljett är den enda vägen som ryms inom rimliga kundantal** — och hög biljett kräver förtroende, vilket är det minst automatiserbara som finns.

---

## 4. Vad "0 kr" och "autonomt" betyder i praktiken

### 4.1 Gratisnivåerna räcker — för produktion, inte för tillväxt

| Resurs | Gratis | Räcker till |
|---|---|---|
| Cloudflare Workers | 100 000 req/dag, 10 ms CPU/anrop | En API-tjänst med måttlig trafik |
| Cloudflare D1 | 5M läsningar/dag, 100k skrivningar/dag, 5 GB | Databas för tusentals kunder |
| Cloudflare R2 | Egen gratisnivå (efter aktivering) | Datasets, loggar, exports |
| Cloudflare Cron | 5 scheman per konto | Autonoma loopar (scout, prissättning, self-check) |
| Workers AI | **10 000 neurons/dag** (~130k tokens för llama-3.1-8b) | ~50–200 små agentuppgifter/dag |
| Groq | 1 000 req/dag, 200k tokens/dag | Samma, snabbare |
| Gemini Flash | Gratisnivå utan kort | Samma |
| Render | Free plan (som AIM) | Kallstart ~50 s — dödar uptime-löften |

### 4.2 Inferensfällan

Cloudflare tar **$0.011 per 1 000 neurons** över gratisnivån. Ett litet LLM-svar på ~1 000 neurons kostar alltså $0.011. Säljer du det för $0.01 **förlorar du pengar på varje anrop** — och gratisnivån tar slut efter ~10 000 neurons, det vill säga ungefär 10 sådana anrop.

Konsekvensen styr hela idén: **sälj data du redan har, inte text du genererar**. Cachad data har marginalkostnad ~0; genererad text har en marginalkostnad som är högre än det pris marknaden betalar. Det är därför AIM:s modell (hämta en gång, servera många) är rätt, och därför "AI som svarar på allt" är fel.

### 4.3 Autonomitrappan

| Nivå | Vad som är automatiserat | Exempel |
|---|---|---|
| 1 | Drift och schemaläggning | Cron som hämtar data |
| 2 | Produktgenerering | Scout som skapar endpoints (AIM i dag) |
| 3 | Prissättning och kvalitetsbeslut | Quality gate, fallback, självcheck |
| 4 | Försäljning till självbetjäning | Listning + 402 + checkout utan människa |
| 5 | Relation och förtroende | Upphandling, avtal, eskrow — **ingen har löst detta** |

Alla idéer nedan når nivå 4. Ingen når nivå 5. Det är precis därför $500k kräver antingen volym (nivå 4 räcker) eller en människa i början (nivå 5).

---

## 5. Fyra affärsidéer

### Idé 1 — Datafabriken: autonoma smaldata-produkter på Apify + x402 + MCP

**Vad den säljer:** 30–100 mycket smala dataprodukter (en sajt, en marknad, en datakälla per produkt), som strukturerad JSON via Apify Actors, x402-endpoints och MCP-verktyg.

**Varför 0 kr:** Cloudflare/Render gratisnivåer, publik data, cron-loopar, ingen LLM i svaret. AIM:s arkitektur är i praktiken redan denna maskin.

**Autonom loop:** cron hittar ny källa → validerar schema → publicerar actor/endpoint → sätter pris → mäter anrop → prissänker eller avvecklar. Allt i kod; LLM bara för att skriva beskrivningar, vilket ryms i gratisnivån.

**Prismodell:** $5–50 per 1 000 rader (Apify PPE) och $0.01–0.05 per anrop (x402). USDC på Base via x402; Apify betalar ut i fiat (PayPal/Wise), vilket är en kompromiss mot kravet på krypto.

**Väg till $500k:** 100 produkter × $417/månad. Det är möjligt i teorin — en utvecklare på Apify har hundratals aktörer — men bevisen säger att medianaktören bland de 900 mest använda tjänar **$14/månad** och att bara 35 av 829 klarar $1 000. Realistiskt utfall: **$500–5 000/månad** efter 6–12 månader.

**Bevis:** Apify delar ut $1,4–1,6M/månad; toppskapare > $10k MRR; en nischad CRE-dataprodukt gick från $56 till $178/månad på två månader (93 % marginal).

**Risk:** Apify äger checkouten och kan ändra villkoren (uthyrningsmodellen stängdes 1 oktober 2026). x402-delen ger nästan inga anrop utan listning.

**Dom: 7/10 som kassamotor. 2/10 som väg till $1M.**

---

### Idé 2 — B2B-datalicens: en smal dataset som 8–20 företag betalar $2 000–25 000/månad för

**Vad den säljer:** *en* dataset med garanterad färskhet och kvalitet, licensierad till företag — inte per anrop. Kandidater som går att bygga med AIM-liknande pipeline och noll datakostnad:

- **Base L2 likviditets- och poolkvalitet** (färskhet, koncentration, nya pooler, wash-handel) till tradingdesks och agentbyggare.
- **Agent- och crawler-telemetri**: vilka AI-agenter som läser vilka sajter, hur ofta, med vilken betalvilja — sålt till publishers, CDN:er och SEO-bolag. Kräver honeypots, inte kapital.
- **x402-pris- och driftsindex** sålt till infrastrukturbolag och fonder. (x402-trust och x402stats publicerar gratis — svag betalvilja.)

**Varför 0 kr:** datan är publik, pipelinen finns i AIM, distributionen är en HTTP-endpoint med API-nyckel eller x402.

**Autonom loop:** insamling → kvalitetsgrind → schemalagd leverans (S3/R2/Webhook) → faktura i USDC → avbrott om betalning uteblir. Support är den enda mänskliga restposten.

**Prismodell:** $2 000–25 000/månad i USDC, årsavtal. Motsvarar 8–20 kunder för $500k.

**Bevis:** `surplusintelligence` $170k/30 d från 31 betalare (~$5 500/payer), `rozo` $77k från 3 betalare (~$25 700/payer), `vapinetwork` $68k från 24 (~$2 800/payer). Hög biljett per betalare är alltså dokumenterad i just detta ekosystem.

**Varför det är svårt:** de tre första kunderna kräver att någon svarar på e-post, visar provdata och skriver ett avtal. Det är nivå 5 i autonomitrappan, och det finns inget bevis för att en agent klarar det. Autonomin börjar på kund 4.

**Dom: 6/10 genomförbarhet, 9/10 som enda realistiska $500k-väg. Autonomi 3/5.**

---

### Idé 3 — Abonnemangsanalytikern: AI-persona med betald kanal i USDC

**Vad den säljer:** daglig, granskad analys (on-chain, Base, x402-ekosystemet) i en betald kanal eller nyhetsbrev, $49–99/månad, betalt i USDC (Cherry, Telegram Stars + krypto-bot).

**Varför 0 kr:** text + data från egna pipelines, publik kanal för distribution, USDC-betalning utan PSP.

**Autonom loop:** pipeline samlar → LLM skriver utkast → deterministiska faktakontroller (priser, siffror, källor) → publicering → prenumerationskontroll → churn-analys. Granskningen är kod, inte människa.

**Väg till $500k:** 695 prenumeranter à $60. Med 8–15 % månatlig churn krävs ~1 000–1 400 gross och, vid 1–3 % konvertering, **35 000–100 000 engagerade följare**.

**Bevis:** crypto-nyhetsbrev på toppnivå tar $430k–810k/år med ~30k prenumeranter; typiska betalkanaler ligger på $500–3 000 MRR; toppnisch $20k–100k.

**Risk:** distributionsberoende (X/Telegram kan stänga av en AI-persona), förtroende (en agent som har fel en gång tappar 20 % på en vecka), och juridik (finansiell rådgivning). Detta är den enda idén med konsumentvolym, och den enda som kräver ett varumärke.

**Dom: 5/10. Hög variantspridning; bra som distributionsmotor, dålig som primär plan.**

---

### Idé 4 — Utförandeagenten: bounties, audit-tävlingar och arbitrage

**Vad den säljer:** resultat, inte data — buggar, rapporter, fyllda ordrar.

**Varför 0 kr:** inget kapital krävs för bounties; verktygen är öppna.

**Bevisen är brutala:** 24 finansierade agent-bounties värda $771 totalt; 161 bidrag för ett $2-pris; en marknadsplats hade betalat ut **$74** under hela sin livstid. Audit-tävlingar har minskat 83 % sedan 2024 samtidigt som bidragen ökat 24 %, Immunefi förbjuder AI-genererade rapporter, Cantina kräver validering och KYC, och Code4rena kör sedan 2025 en egen AI-revisor som tar de lätta fynden ur prispotten. Trading: LLM-agenter gjorde −16 % till −31 % på Kalshi; bara 3 av 22 modeller var i vinst i oktober; 3 % av kontona tar 27 % av vinsten.

**Dom: 1/10 som plan. Möjlig som lottsedel med hårt kostnadstak — inte som intäktsmodell.**

---

## 6. Varför den enda $1M-vägen inte är autonom — och tvärtom

| Om du vill... | Måste du ha... | Kan AI äga det? |
|---|---|---|
| 8,3M anrop/månad à $0.01 | Distribution i klass med CoinGecko | Nej — kräver år av SEO/partnerskap |
| 15 B2B-kunder à $5 500 | Förtroende, avtal, provdata | Nej i början; ja från kund 4 |
| 1 400 prenumeranter à $60 | Publik och varumärke | Delvis — men distributionen är mänsklig |
| 20 % avkastning på $5M | Kapital och edge | Nej — och kapitalet finns inte |
| Infrastruktur åt 37 000 säljare | Att säljarna har pengar | Nej — de tjänar $0.01/månad |

Det finns ingen rad där alla tre kraven (0 kr, autonomt, $1M) möts. Det finns däremot en rad där två av tre möts: **0 kr + autonomt ger $500–5 000/månad** (Idé 1), och **0 kr + $500k kräver en människa i 3–6 månader** (Idé 2).

---

## 7. Rekommenderad portfölj och 90-dagarsplan

**Fördelning av tid:** 60 % Idé 1 (kassaflöde), 30 % Idé 2 (målet), 10 % Idé 3 (distribution). Idé 4 avstås.

| Fas | Dagar | Vad som ska vara klart | Grind |
|---|---|---|---|
| 1 | 0–30 | 10 dataprodukter live på Apify + x402 + MCP; listning i Bazaar/x402scan; första externa betalning | ≥ 1 betalande plånbok utanför egna adresser |
| 2 | 31–60 | 3 kandidatdatasets för B2B; 20 utskick med provdata; prissättning testad | ≥ 2 samtal med potentiell B2B-köpare |
| 3 | 61–90 | 30 produkter; en betald B2B-pilot; kanal med 500 följare | ≥ $500/månad i faktisk intäkt **eller** ett signerat pilotavtal |

**Kostnadstak:** $0 i verktyg, 15 h/vecka, högst $50 i domän/hosting om gratisnivån inte räcker. Inga annonser, ingen betald data, inga token.

**Om grind 3 misslyckas:** behåll Idé 1 som passiv kassaflödeskälla och lägg ned $1M-anspråket. Det är ett ärligt utfall, inte ett misslyckande — det är den förväntade utfallsfördelningen.

---

## 8. Vad som måste vara sant för $500k — prövbart

| Antagande | Tröskel | Om falskt |
|---|---|---|
| B2B-köpare betalar $2 000+ för denna data | 2 av 20 utskick blir samtal, 1 pilot | Byt dataset, inte budskap |
| En dataprodukt kan säljas utan säljare | ≥ 5 köp från okända plånböcker/månad | Autonomin är en illusion; acceptera sälj |
| Apify/x402 ger distribution | ≥ 100 körningar/månad/produkt | Bygg egen kanal eller lägg ned |
| Gratisnivåerna räcker | < 60 % av kvoten förbrukad vid 10× trafik | Inför pris innan du skalar |
| En agent kan sköta support | < 5 % eskaleringar | Budgetera 2 h/vecka |

---

## 9. Ärlig slutsats

**$1M/år är inte en plan, det är en önskan** — givet 0 kr, full autonomi och 12 månader. Marknaden 2026 visar att autonoma mikrosäljare tjänar tio- till hundratusentals gånger mindre än så, och att de som tjänar $100k+/månad är bolag med produkt, säljteam och kapital som lagt till x402 som betalväg.

**Det som däremot är sant, och som AIM redan bevisat:** en ensam utvecklare kan bygga och driva en autonom, kryptobetalad datatjänst för nära noll kronor, med kvalitetsgrindar och självcheck. Det är en sällsynt kompetens och en bra grund.

**Rekommendationen i en rad:** bygg Idé 1 för att bevisa att maskinen kan tjäna sina egna kostnader, och lägg sedan allt krut på Idé 2 — för det är den enda vägen där $500k inte är matematiskt orimligt, och den enda där en människa behövs i högst tre månader.

**Om du vill ha ett enda mål som är både ärligt och ambitiöst:** $10 000/månad inom 12 månader, med $500k som treårsmål och en uttalad insikt om att det kräver antingen en säljfunktion eller en publik.

---

## 10. Källor

- x402stats, State of x402 oktober 2026 — https://x402stats.io/reports/2026-10
- x402stats, september 2026 — https://x402stats.io/reports/2026-09
- Circadian, x402 Bazaar-mätning — https://circadian-agent.com/research/x402-market
- cp0x, Bazaar-rapport 2026-10-21 — https://x402.cp0x.com/reports/x402-bazaar-2026-10-21
- x402-trust, topp-intjänare — https://x402-trust.com/trust/report
- FiatDock, MCP/x402-intäkter — https://fiatdock.com/monetize-mcp-server.html
- ChainWard, Virtuals ACP — https://chainward.ai/decodes/virtuals-top-dog
- Surplus Intelligence, x402-dokumentation — https://www.surplusintelligence.ai/docs/payments/x402
- BlockBooster via HTX, crypto-AI-intäkter — https://www.htx.com/news/crypto-ais-trillion-tokens-only-87-million-in-monthly-revenu-BhQkziNv
- Apify, utbetalningar och villkor — https://apify.com/partners/actor-developers
- Apify-mätning av 900 aktörer — https://dev.to/nikita_iakovlev_415524c19/i-measured-900-apify-actors-and-got-the-price-wrong-by-100x-heres-the-corrected-data-3418
- MCP-monetarisering — https://mcp-marketplace.io/blog/state-of-mcp-monetization-2026 och https://arte.itlibra.com/en/articles/can-mcp-servers-be-monetized
- Agent Bounty Feed — https://dailydollar-bot.github.io/agent-bounty-feed/report/
- Audit-tävlingar och AI-regler — https://github.com/munimtechnologies/audit-contest-ai-rules
- LLM-trading — https://theagenttimes.com/articles/ai-agents-enter-prediction-markets-with-mixed-returns-and-bi-f16846ef och https://www.traderank.ai/llm-trading-benchmark
- Betalda kanaler — https://easy-post.app/en/blog/telegram-bot-business-models
- Crypto-nyhetsbrev — https://www.substats.io/category/crypto
- Cloudflare Workers AI-priser — https://developers.cloudflare.com/workers-ai/platform/pricing
- Cloudflare Workers gratisnivå — https://developers.cloudflare.com/workers/platform/pricing
- Groq gratisnivå — https://klymentiev.com/blog/groq-pricing
- Google scaled content abuse — https://developers.google.com/search/docs/essentials/spam-policies
---

## 11. Tillägg 9 november 2026 — reviderad rekommendation med delvis autonomi

*Detta avsnitt uppdaterar avsnitt 5–9. Där de säger olika gäller detta avsnitt.*

### 11.1 Vad undantaget från 100 % autonomi ändrar

Med kravet på full autonomi var B2B-datalicensen omöjlig att starta, eftersom de tre första kunderna kräver samtal. Med ett undantag blir den **den snabbaste vägen till $1 000 netto**: en enda kund à $1 200–1 500/månad klarar målet, medan datafabriken behöver cirka 30 produkter för samma summa.

Autonomi är därför inte längre ett filter på idéer, utan en **kostnadspost**. Frågan blir: vilka timmar måste vara mänskliga? Svaret är tre — välj nisch, sälj in de första 1–3 kunderna, skriv avtalet. Allt annat (insamling, kvalitetsgrind, leverans, fakturering, övervakning, rapportering) kan vara kod.

**Ny rangordning:**

| Idé | Tidigare roll | Ny roll |
|---|---|---|
| Agent Readiness (ny) | fanns inte | **Kil: första intäkten, högst biljett per timme** |
| B2B-datalicens | fas 2 | Intäktsryggrad, säljs till samma kunder |
| Datafabriken | primär | Autonom bas och lång svans |
| Abonnemangsanalytikern | 10 % | Distribution, senare |
| Utförandeagenten | avstås | avstås fortfarande |

### 11.2 En pipeline, fyra ytor

| Yta | Köpare | Pris | Autonomi | Roll |
|---|---|---|---|---|
| Fri publik index (webb + MCP + `llms.txt`) | Agenter, utvecklare, sökmotorer | $0 | 100 % | Distribution och trovärdighet |
| Apify-aktörer | Företag som kör scraping-jobb | $5–50/1 000 rader | 95 % | Volym, fiat, lång svans |
| x402-endpoints | Autonoma agenter | $0.01–0.25/anrop | 100 % | Agent-native, noll registrering |
| Licensierad feed / monitorering | Företag med budget | $350–2 000/mån | 85 % | **Intäktsryggraden** |

Marginalkostnaden för en extra yta är nära noll, och varje yta når en köpare de andra inte når. Det är kombinationen — inte fyra separata bolag. Kombinera dock inte tre pipelines: Apify-portföljen ska sälja **samma** data som auditen probar.

### 11.3 Vad $1 000 netto kräver per yta

| Väg | Volym för $1k netto | Tid till första intäkt |
|---|---|---|
| En licensierad feed | 1 kund à $1 200/mån | 4–8 veckor (med sälj) |
| Monitoreringsabonnemang | 3 kunder à $350/mån | 6–10 veckor |
| Audit + monitorering | 1 audit à $1 500 + 1 abonnemang | 2–4 veckor |
| Apify-portfölj | ~30 produkter à $40 netto | 3–6 månader |
| x402 ensamt | 20 000 anrop/mån à $0.05 | 6–12 månader, osannolikt |

Slutsatsen är densamma som i avsnitt 3, men skarpare: **sälj få, dyrt — automatisera leveransen.**

### 11.4 Produktlinjen: Agent Readiness

Kilen är inte ännu en data-API. Det är den enda produkten där AIM:s erfarenhet är själva varan: vi vet hur en 402-envelope ska se ut i v2, hur Bazaar-listning fungerar, vad som krävs i `llms.txt`, `agents.json` och MCP-manifest — och vi har själva hittat felen i vår egen yta. Nästan alla x402-säljare har trasiga envelopes; det finns ett öppet spår som heter just "402 envelope issues".

**1. Audit — $1 500 engångs.** Vi probar hela kundens agentyta och levererar en rapport med konkreta fixar. Tio kontroller:

1. 402-svaret: `PAYMENT-REQUIRED` i v2, base64, CAIP-2, belopp, `payTo`, asset, timeout.
2. Klientkompatibilitet: kan en riktig x402-klient betala — inte bara en tx-hash?
3. Kvitto: skickas `PAYMENT-RESPONSE` efter settle?
4. Discovery: `/.well-known/x402`, Bazaar-listning, `llms.txt`, `agents.json`, A2A-kort.
5. MCP: verktygsschema, beskrivningar, latens, felformat.
6. Kataloger: x402scan, Glama, PulseMCP, mcp.so — finns de där agenterna letar?
7. Latens p50/p95 och uptime över 30 dagar.
8. Felhantering: 4xx/5xx, `Retry-After`, rate limits.
9. Prisdokumentation: stämmer priset i 402-svaret med dokumentation och katalog?
10. Säkerhet: replay-skydd, signaturvalidering, inga interna fält i svaret.

**2. Monitorering — $350/mån.** Samma prober varje timme, larm vid avvikelse, månadsrapport. Här blir affären autonom: inget nytt säljarbete, bara drift.

**3. Dataproduct — $1 200/mån.** Den underliggande Base-datan licensieras till samma kunder när de väl litar på oss.

AIM blir fallstudie nummer ett: vi visar våra egna fynd (blandade v1/v2-huvuden, avsaknad av Bazaar-listning, tomma mätvärden vid 429) som bevis på att metoden hittar verkliga fel.

### 11.5 Kalkyl och tidsåtgång

Tre monitoreringskunder plus en audit i kvartalet ≈ **$2 550/månad**:

- 3 × $350 = $1 050/mån
- 1 audit per kvartal = $1 500 / 3 = $500/mån
- Summa ≈ $1 550/mån — plus en licensierad feed à $1 200 ger **$2 750/mån**

Med cirka 10 timmar i veckan (40 h/mån) är det ~$60/h, och timkostnaden sjunker varje månad eftersom abonnemangen förnyas utan nytt arbete. Vid $1 000 netto för 40 timmar är timpenningen ~$25 — under en utvecklartimme, men över noll, och den stiger när abonnemangsstocken växer.

**De tre mänskliga handlingarna, totalt ~6 timmar:** välj nisch, skicka 30 mejl med en provrapport, skriv första avtalet. Sedan tar maskinen över.

### 11.6 Tolvmånadersbana

| Månad | Fokus | Netto/månad |
|---|---|---|
| 1 | Pipeline, fri index, AIM som fallstudie | −$10 |
| 2–3 | 10 auditar (2 betalda, 3 rabatterade), första monitoreringen | $1 000–1 500 |
| 4–6 | 5 monitoreringskunder, 20 Apify-produkter | $2 500–3 500 |
| 7–12 | 2 licensierade feeds, 60 produkter, agentdriven säljtratt | $6 000–10 000 |

$1M är fortfarande en önskan, inte en plan. **$10k/månad vid månad 12 är den rimliga ambitionen**, med en svans: en enda kund som betalar $5 000/mån för en feed förändrar kalkylen mer än 200 Apify-produkter.

### 11.7 Vad som inte ska kombineras

- Ingen andra pipeline: allt ska sälja samma data.
- Inga bounties, audit-tävlingar eller trading: lotterier eller kapitalbundna, och reglerna utesluter allt oftare AI.
- Ingen betald annonsering innan en enda kund betalat.

### 11.8 Kill-kriterium

Om vi efter 60 dagar inte har **en** betalande kund på auditen är inte problemet priset — då är agent-beredskap ännu inte ett köpt problem. Då faller vi tillbaka på Apify-portföljen som kassaflöde och behåller indexet som distributionsasset.

### 11.9 Ordlista för den som är ny

| Term | Betyder i praktiken |
|---|---|
| **x402 / 402-svar** | Webbsvaret "betala först": servern säger pris och hur betalningen ska se ut |
| **402-envelope** | Själva kuvertet med priset — är det felformat förstår agenten ingenting |
| **PAYMENT-REQUIRED / PAYMENT-SIGNATURE** | Kuvertet respektive agentens underskrift som gör betalningen |
| **Discovery-manifest** | Maskinläsbar meny över vad tjänsten säljer (`llms.txt`, `agents.json`, `/.well-known/x402`) |
| **MCP** | Standard som låter AI-klienter anropa verktyg; ett manifest beskriver verktygen |
| **Bazaar** | Coinbases katalog där agenter hittar betalbara tjänster |
| **Probe** | Automatiskt testanrop som kontrollerar att allt svarar som det ska |
| **USDC på Base** | Dollarmynta på Base-nätverket; betalning sker direkt till plånbok utan kortinlösen |
