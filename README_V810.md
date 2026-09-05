# Lofthus Road Open V810 · Design Reset

V810 bygger direkte på V801. Denne versjonen er først og fremst en stor design- og UX-rebuild. LiveState, newsroom, routing, historikk og analysefunksjonene fra V801 er beholdt, men fronten er bygd om rundt ett prinsipp:

**Sportsnettsted først. Analyseverktøy når brukeren vil dykke dypere.**

## Hva som er endret

### 1. Forsiden er bygd om

Under en aktiv GW vises nå én samlet matchday-flate øverst:

- stor LIVE-hovedsak
- spillerbilde av spilleren som driver historien
- kampstatus
- GW-poeng, eierskap og kapteinsdata
- managers som påvirkes mest av spilleren
- Topp 5 ved siden av hovedsaken på desktop

Dermed ligger ligaens viktigste informasjon over bretten uten at siden starter med en stabel tekstblokker.

Når GW ikke er live, går forsiden rett til Topp 5 og redaksjonelle Snakkiser.

### 2. Premier League-spillerbilder

`player_catalog()` lagrer nå spillerens `code` og bygger et bilde-URL-felt fra Premier Leagues spillerressurser. `image_url` følger spilleren videre gjennom ownership- og LiveState-modellen.

Bildene brukes i:

- LIVE-hovedsaken
- Snakkiser
- Mest populære
- spillerprofil
- managerens lagoppstilling

Hvis en spiller mangler bilde-URL, faller UI tilbake uten å stoppe siden.

### 3. Snakkiser er blitt en visuell sportsfeed

Snakkiser vises ikke lenger som fire like tekstlinjer. V810 bruker en redaksjonell grid:

- én stor hovedsak
- mindre sekundærsaker
- spillerbilder når historien handler om en spiller
- korte statusmarkører som LIVE / Ferdig / Analyse
- ingen synlig intern importance-score

Den underliggende newsroom-logikken og persistence-reglene fra V801 er beholdt.

### 4. Topp 5 har fått tydeligere sportslig hierarki

- lederen har større visuell vekt
- livebevegelse og GW-poeng er sekundærinfo
- manager-menyene er beholdt
- under LIVE ligger Toppen sammen med hovedsaken i stedet for langt under den

### 5. Mest populære er blitt spillerkort

Tre kompakte spillerkort med:

- spillerbilde
- navn og klubb
- Lofthus-eierskap
- antall eiere og kapteiner

Hvis ingen personlig manager er valgt, bruker denne seksjonen full bredde i stedet for å etterlate en tom kolonne.

### 6. Managerprofil og lagoppstilling

Managerprofilen er ryddet visuelt og lagoppstillingen bruker nå spillerbilder inne på banen. C, VC og TC, live-status og poeng er beholdt.

Sekundære historikk-/chip-/karrieredata ligger fortsatt bak expanders. Hovedinnholdet er laget og situasjonen akkurat nå.

### 7. Spillerprofil

Spillersiden har fått en stor sportslig hero med:

- spillerbilde
- klubb/kampstatus
- GW-poeng
- LRO-eierskap
- kapteiner

Dybdeanalysen ligger under heroen.

### 8. Analyse er bevisst sekundært

Hovednavigasjonen er nå:

- Forside
- Ligaen
- Hall of Fame
- Analyse

`Analyse` leder til Rivalradar. Det gjør analyseverktøyet enkelt å finne uten at hele produktet presenterer seg som et dashboard ved første møte.

### 9. Kompakt manager-velger

Den gamle brede manager-selecten på forsiden er erstattet av en kompakt popover. Identitetsfunksjonen er den samme, men den okkuperer ikke lenger nesten en hel rad.

### 10. Nytt designsystem

`lro_ui.py` bruker nå et samlet visuelt system med:

- roligere varm bakgrunn
- mørk marine som sportslig hovedflate
- gull som aksent
- færre harde rammer
- større typografiske kontraster
- redaksjonelle layouts
- responsive desktop/tablet/mobile-regler

Det er bevisst mindre dashboard-estetikk og mer sportsmedie-estetikk.

## Hva V810 ikke gjør

V810 er ikke en ny feature-runde. Den skal ikke endre hvem som har hvilke poeng eller omskrive LiveState-reglene.

Følgende kjerne er videreført fra V801:

- én autoritativ LiveState
- kaptein / TC / chips / hits
- live ranking
- månedsranking
- newsroom persistence
- managerprofiler og manager-meny
- Rivalradar
- browser/deep-link routing
- Hall of Fame/historikk
- 2024/25-bronsen til Rasmus Grytvik-Skoglund

## Mobil

Ved mindre skjermer:

- LIVE og Topp 5 stables
- newsroom går over til én kolonne
- ligatabellen skjuler sekundærkolonner
- spillerkort stables
- lagoppstillingen bruker mindre spillerfliser
- manager-meny åpnes som en bred mobilmeny nederst

## Deploy

1. Pakk ut `LRO_V810.zip`.
2. Kopier innholdet i repo-roten.
3. Behold eksisterende `data/` og andre persistente historikkfiler.
4. Deploy som før via Streamlit/Render.

Ingen nye Python-avhengigheter er lagt til. `requirements.txt` er fortsatt Streamlit, pandas og requests.

## Viktig om spillerbilder

Spillerbildene lastes fra en ekstern Premier League-ressurs i nettleseren. Hvis den ressursen er midlertidig utilgjengelig, skal resten av produktet fortsatt fungere. Bilder er presentasjon, ikke datakilde for poengberegningen.
