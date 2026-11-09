# Konkurrensanalys — AIM Network (johngarp.click)

*Underlag: egen läsning av kodbasen (commit 8b56b0a), live-anrop mot produktionen 9 november 2026, samt extern research om x402-ekosystemet, krypto-Data-API:er och MCP-marknaden. Siffror från tredje part är citerade med källa och datum; de är ögonblicksbilder, inte garantier.*

---

## 1. Sammanfattning för den som har bråttom

1. **Marknaden är inte "krypto-Data-API:er".** Det är tre separata marknader som råkar mötas i vår produkt: (a) data-API:er med abonnemang (CoinGecko, Birdeye, Nansen), (b) x402-betalda mikro-API:er för agenter, (c) MCP-verktyg för LLM-klienter. Konkurrensen ser helt olika ut i varje lager, och vi tävlar i alla tre samtidigt — vilket är vår svaghet.
2. **x402-marknaden är liten, ung och extremt topptung.** I oktober 2026 fanns 91 företag med organisk intäkt på x402, $793k organisk volym på 30 dagar, och de tio största tog 76 % av volymen. Medianförsäljaren tjänade **$0.01 på en månad** ([x402stats, okt 2026](https://x402stats.io/reports/2026-10)). Det är den enda siffra som bör styra vår förväntan.
3. **Vår produkt är tekniskt konkurrenskraftig men kommersiellt osynlig.** Live-verifierat: en standard x402 v2-klient kan betala oss (vår testnyckel avvisades av facilitatoren med `invalid_exact_evm_signature`, alltså körs verify/settle skarpt). Men vi finns inte i Coinbase Bazaar och svarar tomt i x402scan-sökning — vi är alltså protokollkompatibla men inte upptäckbara där agenterna letar.
4. **Vårt pris är fel positionerat i två av tre fall.** $0.01 för crypto-pulse ligger på marknadsnivå (CoinGecko tar $0.005 för motsvarande), $0.05 för radar/trending är rimligt, men **$1.00 för deep-market-report är 2–10× över vad jämförbara betalda rapporter kostar** (Messari $0.10–0.75, Glassnode $0.05 per metric).
5. **Ärlig rekommendation:** sluta tävla om "generisk kryptodata". Välj en nisch där vi faktiskt är ensamma — *Base L2, agent-native, med datakvalitetsgaranti och kvitto* — och lägg 80 % av nästa månads arbete på distribution (Bazaar, x402scan, MCP-register, riktiga betalare), inte på fler endpoints.

---

## 2. Hur konkurrensen fungerar

### 2.1 Tre lager, tre olika spel

| Lager | Vem äger det | Intäktsmodell | Vad som avgör vinst |
| --- | --- | --- | --- |
| **Abonnemangs-API** | CoinGecko, CoinMarketCap, Birdeye, Nansen, Kaiko, Amberdata, Glassnode | Månadsplan $29–499+, credits | Datadjup, historik, varumärke, SLA, säljteam |
| **x402-mikro-API** | Tusentals små operatörer + de stora som lagt till x402 som sidoingång | Per anrop, $0.001–0.75 | Upptäckbarhet, pris, latens, att faktiskt leverera |
| **MCP-verktyg** | CoinGecko, Nansen, Birdeye, CoinMarketCap m.fl. + tusentals indie-servrar | Nästan alltid gratis; betalt via underliggande API-nyckel | Listning i register, verktygsbeskrivning, att bli vald av modellen |

Vi ligger i alla tre lagren samtidigt: vi har ett abonnemangsliknande VIP-pass, x402-betalning per anrop OCH en MCP-server. Det är en styrka i berättelsen och en svaghet i fokus — varje lager kräver olika distribution.

### 2.2 Hur pengarna faktiskt rör sig (det viktigaste avsnittet)

Flera oberoende mätningar pekar åt samma håll:

- **x402stats (okt 2026):** 91 organisk-intäktsföretag (+13), $793k organisk volym (−32 %), 76 % av volymen i topp 10 plånböcker, medianförsäljare **$0.01/månad**, ~0 dagliga betalande agenter i snitt.
- **Bazaar-indexet kopplat till kedjan (aug 2026):** 15 257 listningar; av 1 075 unika betalningsadresser på Base fick **46,5 % ingenting** under ett 4,1-dagarsfönster; median **$0.01**, 90:e percentilen **$1.53** ([agentatwork/x402-revenue](https://github.com/agentatwork/x402-revenue)).
- **Crawl Census (maj 2026, via [dev.to](https://dev.to/soloearn/how-much-do-x402-sellers-actually-earn-5hk2)):** ca **$26/månad per försäljare** i snitt över ~43 000 försäljare; bästa enskilda $3.12k/30 dagar.
- **TRM Labs (sep 2026, samma artikel):** $52.7M totalt sedan maj 2025, varav ca hälften försvinner när självbetalningar och bulkflöden rensas; **0,6–7,5 % bedöms agentiskt**, motsvarande **$5k–11k/månad för hela marknaden**.
- **Enskilda jämförbara säljare** ([tools.tx402.io](https://tools.tx402.io/compare/market-data)): ApiToll Crypto Prices $0.001/anrop → 469 anrop och 29 betalare på 30 dagar. Hyperliquid Market Data $0.01 → 7 anrop och 5 betalare på 30 dagar.

**Slutsats:** det finns ingen "x402-marknad" att ta andelar i ännu. Det finns en demonstrationsmarknad där några tiotal operatörer tjänar riktiga men små pengar, och en lång svans som tjänar noll. Att bygga fler endpoints ökar inte intäkten — bara antalet saker ingen hittar.

### 2.3 Hur de stora spelarna faktiskt konkurrerar

- **CoinGecko** har lagt till x402 ($0.005/anrop) *och* en keyless MCP-server ([docs](https://docs.coingecko.com/docs/mcp-server)). De prissätter x402 under vårt $0.01 och ger bort MCP-åtkomst. Deras försvar är djup, inte pris: 90+ endpoints, 13 års historik, 2 500 req/min på topplan.
- **CoinMarketCap** ligger på $0.01/anrop i x402 med 54M+ tillgångar och MCP — exakt vår prisnivå för pulse, men med oändligt mycket mer data.
- **Birdeye** säljer $39–499/månad med 2,5M–60M compute units och har officiell MCP i beta. De äger Solana-djupet.
- **Nansen** säljer credits ($10/10 000) och en MCP-server med 53 verktyg, inklusive premiumetiketter till 150 credits/anrop. De äger *vem som handlar*, inte *vad priset är*.
- **Glassnode** har x402 på $0.05 per metric och $0.01 för metadata — exakt vår radarprisnivå, men med on-chain-fundamenta.
- **Messari** ligger på agentic.market med $0.10–0.75 per anrop för research-data.
- **DexScreener** är gratis (60–300 req/min, ingen MCP, ingen historik) och är därför den vi *återförsäljer* — vilket är hela vår affärsmodell i dag och hela vår risk.

**Mönstret:** alla stora aktörer använder x402 som *kundvärvning*, inte som affärsmodell. Deras intäkt kommer från abonnemang. Vi försöker göra x402 till affärsmodell utan abonnemangsbackning — det är en mycket svårare position.

### 2.4 Hur MCP-konkurrensen fungerar

- MCP-specifikationen har **ingen betalningsprimitiv**; 95 %+ av publika servrar är gratis ([Spawnpay](https://spawnpay.ai/blog/the-mcp-monetization-gap)). Att ta betalt kräver egen mätning eller en gateway.
- **Smithery stängde sin MCP-proxy och managed identity 31 oktober 2026** — distribution via tredjepartsproxy är inte en trygg kanal.
- Nischade krypto-MCP:er finns redan: t.ex. *Rug Munch Intelligence* med 117 verktyg som aggregerar DexScreener, Birdeye, GMGN, Arkham, Nansen, Dune och Jupiter, från $0.001/anrop ([TOLL·402](https://toll402.com/tool/rug-munch-intelligence)). De slår oss på bredd med två storleksordningar.
- Glama listar 42 416 servrar ([Glama](https://glama.ai/mcp/connectors)). Att bara finnas i ett register ger noll trafik; man måste bli *vald* av modellen, vilket avgörs av verktygsbeskrivning, pålitlighet och pris.

---

## 3. Succefaktorer — vad som faktiskt avgör vinst

Rangordnade efter hur mycket de förklarar observerad framgång:

1. **Distribution före produkt.** De som tjänar pengar är listade i Bazaar, x402scan, agentic.market och/eller MCP-register, och deras 402-svar är felfria för en standardklient. Att vara "bäst" utan att vara listad ger noll anrop.
2. **Ren x402-kompatibilitet.** `PAYMENT-REQUIRED` (v2, CAIP-2, base64) → `PAYMENT-SIGNATURE` → settle → `PAYMENT-RESPONSE`. En enda avvikelse och klienten fallerar tyst. Direktavgörande.
3. **Pris inom $0.001–0.05 för "en fråga, ett svar".** Allt över $0.10 kräver att svaret är en *slutsats*, inte ett datablad.
4. **Latens och uptime.** p95 under ~300 ms är normen bland de monitorerade säljarna; 100 % 30-dagars uptime är vanligt. En 503 mitt i en agentloop är dyrare än priset.
5. **Dataproveniens.** `as_of`, `source`, `is_stale`, `data_age_seconds` — de som vinner förtroende kan svara "jag vet inte" i stället för att gissa. Här är vi faktiskt bättre än många.
6. **Bredd som svar på "en agent, en faktura".** Aggregatorer (Spraay, x402node, Rug Munch) vinner för att agenten slipper tio betalflöden. Bredd slår djup i mikrosegmentet.
7. **Frikopplad testbarhet.** `?sample=true`, `?quote=true` och ett gratis teaser-anrop är standardgrepp för att låta agenten verifiera innan den betalar. Vi har det — det är en reell fördel.
8. **Återkommande relation.** VIP-pass och abonnemang vinner över per-anrop när agenten ringer ofta. Men bara om passet går att förstå ur 402-svaret.

---

## 4. Vad de har som vi inte har

| Område | Konkurrenterna | Vi | Effekt |
| --- | --- | --- | --- |
| **Historik** | CoinGecko 13 år, Glassnode hela tidsserier, Birdeye 30B+ trades | Endast nuläge | Kan inte sälja backtest, forskning eller "vad hände sedan" |
| **Bredd** | 500–1 000+ endpoints (x402node), 117 verktyg (Rug Munch), 53 (Nansen) | 5 endpoints + dynamiska slugar | Varje agent har fler skäl att välja dem |
| **Wallet-/aktörsdata** | Nansen 400M+ etiketterade adresser, Birdeye smart money | Inga etiketter | Kan inte svara "vem köper", bara "hur mycket" |
| **Flera kedjor** | Base + Solana + Ethereum + 20–60 nätverk | Base huvudsakligen | Stänger ute majoriteten av agenter |
| **Officiell MCP i register** | CoinGecko keyless, Nansen, Birdeye, CoinMarketCap | Egen `/mcp` + Glama-manifest | Osynlig i de kataloger LLM-klienter faktiskt läser |
| **Bazaar/x402scan-listning** | De flesta seriösa x402-säljare | **Nej** (verifierat: tomt sökresultat) | Noll inflöde från ekosystemets huvudkanal |
| **Abonnemangsbackning** | Alla stora | Endast VIP-pass | Ingen stabil basintäkt, ingen B2B-försäljning |
| **SLA/avtal/faktura** | Enterprise-planer, KYT/OFAC via CDP | Inget | Stänger ute företagskunder helt |
| **Refund-/tvistflöde** | `batch-settlement` med eskrow, eller affärslogik | Ingen återbetalningsväg i kod | En utebliven leverans blir en förlorad kund |
| **Streaming** | WebSocket hos CoinGecko/Birdeye | Polling | Fel produkt för snabba agenter |
| **Eget datainnehav** | Egna noder/indexerare | Återförsäljer DexScreener/CoinGecko | Sårbarhet: 429 från Render-IP:n slår ut hela discovery |

---

## 5. Vad som saknas på marknaden som vi kan skapa

Här är de luckor jag faktiskt kan belägga, med bedömning av genomförbarhet:

### 5.1 Datakvalitet som säljbar produkt (starkast)
Ingen av de stora säljer *osäkerhet*. De säljer tal. En agent som får `null` + `is_stale: true` + orsak kan fatta ett säkert beslut; en agent som får en gissning kan inte. Vi har redan kvalitetsgrinden, `fallback_reason` och proveniensfälten — **det är vår enda genuina differentiering**. Gör det till produkten: `GET /api/v1/quality/{slug}` som säljer "är den här datan färsk, och varför inte" för $0.002, och en signerad payload (`payload_signature`) som en agent kan verifiera utan att lita på oss. Ingen annan i x402-urvalet gör detta.

### 5.2 Kvitto och återbetalning som standard
`exact`-schemat är oåterkalleligt; marknaden löser refunds med affärslogik eller batch-eskrow. En säljare som **automatiskt återbetalar vid utebliven leverans** (vi har redan `PAYMENT_REJECTED`-telemetri och grindar) kan prissätta högre än billigare konkurrenter, för agenten slipper risken. Detta är en positioneringsfråga lika mycket som kod.

### 5.3 "En fråga, ett svar"-paket i stället för datablad
Vår `deep-market-report` för $1.00 är ett datablad med 11 toppnycklar. Marknaden betalar $0.10–0.75 för *slutsatser* (Messari) och $0.05 för *ett* metric (Glassnode). Antingen gör vi rapporten till en tydlig slutsats med confidence och åtgärd ("regim: risk-off, konfidens 0.72, tre skäl") och prissätter $0.25, eller vi lägger ned den. $1.00 för ett datablad är den svagaste punkten i hela prislistan.

### 5.4 Base-specifik long tail
CoinGecko och Birdeye täcker stora kedjor. Base L2:s långa svans av nya pools, Aerodrome-koncentration och veckovis utbetalningar är underbetjänt i agentformat — och vår scout gör redan jobbet. En endpoint som listar *nya Base-pooler senaste 60 minuterna med kvalitetsflagga* är smal, billig att bygga och svår att kopiera utan samma grind.

### 5.5 Router/aggregator ovanpå x402 (störst, svårast)
Ingen dominerande "hitta billigaste pålitliga datakällan och betala åt mig"-tjänst finns; PayAPI Market listar 1 279 verifierade API:er men är en katalog, inte en router ([PayAPI](https://payapi.market/)). En MCP-server som tar emot "BTC-pris med <2 s färskhet", jämför tre leverantörer, betalar den billigaste och tar 20 % spread är en affärsmodell som växer med ekosystemet i stället för att konkurrera med det. Men den kräver kapital, avtal och tillit — realistiskt som *fas 3*, inte nästa steg.

### 5.6 Frikostig gratisnivå med attribution
CoinGecko och DexScreener vinner på friktion; agenter provar gratis. Vårt teaser är ett enda BTC-pris. En gratis nivå på 100 anrop/dag med `Source: AIM Network` som krav skulle ge oss distribution och telemetri — och är den billigaste marknadsföringen som finns i det här segmentet.

---

## 6. Mina egna frågor — med svar

**F1. Varför skulle en agent betala oss $0.01 när CoinGecko tar $0.005?**
Endast av tre skäl: (a) vi svarar på något de inte svarar på (Base-poolers kvalitet och färskhet), (b) vi är billigare i *totalt* antal betalsteg (ett anrop i stället för tre), (c) vi är pålitligare i stunden. I dag har vi bara (a) delvis. Priset är alltså inte problemet — avsaknaden av unikt svar är det.

**F2. Är $2.00 för ett VIP-pass rimligt?**
Ja i absoluta tal, men fel i förpackning. 500 anrop för $2.00 = $0.004/anrop, vilket undersäljer våra egna $0.01–0.05-endpoints med 2,5–12×. Dessutom säger README "1 000 calls" medan `VIP_PASS_MAX_CALLS = 500` — en agent som läser vår egen dokumentation och räknar får fel svar. Det måste stämma innan ett enda pass säljs.

**F3. Kan vi vinna på att vara "ärliga" när alla andra gissar?**
Ja, men bara om ärligheten är *synlig i svaret* och *säljbar separat*. `is_synthetic: true` är rätt gjort, men en agent som får `null` går vidare till nästa leverantör om den inte förstår varför. Proveniens + förklaring + ett kvalitetsdata-endpoint gör ärligheten till en produkt i stället för en ursäkt.

**F4. Bör vi satsa på MCP eller REST?**
Båda, men MCP är distributionskanalen och REST är intäktskanalen. MCP-servrar är nästan alltid gratis; betalningen sker på 402-anropet under. Vår `/mcp` bör därför vara gratis att *lista och beskriva* och bara ta betalt vid `tools/call` — precis den arkitektur vi redan har.

**F5. Är vår största risk konkurrens eller något annat?**
Konkurrens är inte den största risken. Den största risken är att **vi inte får en enda riktig betalning**, och den näst största är **dataeroendet**: DexScreener ger 429 från vår produktions-IP, vilket gör discovery tomt på siffror. Båda är interna problem, inte konkurrentproblem. En konkurrent kan inte göra oss mer skada än vad 0 betalare redan gör.

**F6. Vad skulle få mig att säga att detta inte är värt att fortsätta?**
Om vi efter listning i Bazaar + x402scan + tre MCP-register och en gratisnivå fortfarande har noll betalande agenter efter 60 dagar, då är slutsatsen att marknaden inte är mogen — inte att produkten är fel. Den slutsatsen är värd att köpa för två månaders arbete, men den ska mätas, inte gissas.

---

## 7. Vår position i ett diagram

```
                 HÖGT DATADJUP
                       │
     Kaiko/Amberdata   │   Nansen        CoinGecko/CMC
     (institutionellt) │   (aktörer)     (bredd, abonnemang)
                       │
  HÖGT PRIS ───────────┼────────────── LÅGT PRIS
                       │
     Messari ($0.10–   │   Birdeye ($39/mo)
      0.75/anrop)      │
                       │   ★ AIM Network (i dag: Base-specifik,
                       │     ärlig, osynlig, utan historik)
     Glassnode ($0.05) │   DexScreener (gratis, ingen MCP)
                       │   ApiToll ($0.001, 29 betalare)
                 LÅGT DATADJUP
```

Vi sitter i det mest trängda hörnet: lågt djup, lågt pris, hög konkurrens från gratis alternativ. Den enda vägen ut är att flytta oss uppåt på en axel vi kan äga — **tillförlitlighet och Base-specifik kontext** — inte att flytta oss högerut mot fler endpoints.

---

## 8. Ärlig rekommendation

### Gör detta först (30 dagar) — distribution och trovärdighet

1. **Bli listad.** Registrera Bazaar-extensionen mot CDP-facilitatoren (eller verifiera att PayAI listar oss), skicka in till x402scan, x402-list, agentic.market och Glama. Utan detta är allt annat arbete osynligt. *Detta är den enskilt viktigaste åtgärden i hela analysen.*
2. **Genomför en riktig betalning** med en standardklient (x402-fetch/x402-axios) — inte ett tx-hash — och spara `PAYMENT-RESPONSE`. Det bevisar både för oss och för en katalog att flödet håller.
3. **Rätta prislistan:** README säger 1 000 VIP-anrop, koden 500. Sänk `deep-market-report` till $0.25 eller gör om den till en slutsats. Sätt crypto-pulse på $0.005 för att matcha CoinGecko, eller höj den till $0.02 med ett unikt fält (Base-poolkontext) som motiverar priset.
4. **Publicera en statussida för våra egna feeds** (`/status` finns redan) och länka den från `/llms.txt` och `/agents.json`. Uptime är säljargument i det här segmentet.

### Gör detta sedan (60–90 dagar) — en nisch, inte fem

5. **Bygg "Base L2 agent intelligence"** som en tydlig produktlinje: nya pooler senaste timmen, likviditetskoncentration, kvalitetsflagga, och ett `quality`-endpoint. Det är den enda ytan där ingen av de stora är direkt konkurrenter.
6. **Signera payloads** (Ed25519 över kanonisk JSON + `as_of`) och sälj verifierbarhet. Det är billigt att bygga och omöjligt att kopiera utan samma disciplin.
7. **Lägg en gratisnivå med attribution** (100 anrop/dag). Mät konvertering; förvänta dig under 1 % initialt — en datamarknadsplats rapporterade 1 183 agentprober och 5 betalningar ([dev.to](https://dev.to/soloearn/how-much-do-x402-sellers-actually-earn-5hk2)). Det är normalen, inte ett misslyckande.

### Gör inte detta

8. **Bygg inte fler generiska endpoints.** Marknaden har 15 000 listningar och medianintäkten är en cent. Fler endpoints ökar bara ytan som ingen hittar.
9. **Satsa inte på enterprise/abonnemang ännu.** Utan SLA, faktura och avtal är det en annan produkt med annan säljcykel.
10. **Bygg inte routern (5.5) nu.** Den kräver kapital och tillit; den är fas 3, och bara om vi först bevisar att vi kan få betalt för egen data.

### Förväntansbild (ärlig)

Med dagens marknadsläge är en realistisk intäkt för en enskild x402-säljare med bra listning **$5–50/månad** under de första månaderna, med en lång svans av noll. Det gör AIM Network till ett utmärkt *portfölj- och kompetensbevis* och ett svagt *företag* — om det inte kombineras med en nisch där kunderna redan finns (Base-ekosystemets agentbyggare) eller med en distributionskanal vi kontrollerar. Min rekommendation är därför: behåll produkten, byt måtten. Mät antal betalande agenter och listningar, inte antal endpoints och tester.

---

## 9. Vad jag inte kunnat verifiera

- Om PayAI-facilitatoren vidarebefordrar våra resurser till Bazaar/CDP-discovery. Vår sökning i x402scan gav tomt, men jag har inte kunnat avgöra om det beror på att vi saknas eller på att deras sök-API kräver exakt matchning.
- Faktisk trafik till `/mcp` från riktiga LLM-klienter; `/status` visar `total_calls_served: 0` och instansen är ny.
- Konkurrenternas nuvarande priser i realtid — siffrorna är hämtade från deras publikationer och tredjepartsjämförelser i oktober/november 2026 och kan ändras utan notice.
- Huruvida x402-marknadens organiska volym fortsätter falla (september −46 säljare, oktober +13). En månads data är inte en trend.
