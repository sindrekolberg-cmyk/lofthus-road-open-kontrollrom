# Lofthus Road Open V800
## THE PRODUCT

V800 er en produktrebuild bygget direkte videre på V706. Målet er at Lofthus Road Open skal fungere som ett sammenhengende live sportsprodukt, ikke som en samling Streamlit-paneler.

## Hva som er nytt

### Én live-sannhet
`lro_live.py` bygger én autoritativ `LiveState` for hele ligaen. Den samme managerstaten brukes av forsiden, Topp 5, ligatabellen, managerprofil, Form, månedstabell, Sammenlign og Rivalradar.

Live managerstate inneholder blant annet:
- live GW-poeng
- transfer hits
- live total
- live plassering og bevegelse
- kaptein / Triple Captain / vicekaptein
- aktiv chip
- spillere ferdig, live og igjen
- månedspoeng og månedsplass
- lagverdi og bank

### Ny live-motor
- spillerpoeng/fixtures oppdateres billig under kamp
- picks hentes league-wide i bakgrunnen og gjenbrukes
- picks synkroniseres på nytt ved relevante kampstatusoverganger og med rolig cadence mellom kamper for autosubs/captain fallback
- FPL-klienten har TTL-cache og stale-if-error
- siste gyldige state beholdes mens ny state bygges
- historikk hentes parallelt i bakgrunnen

### Ny forside
Prioriteten er nå:
1. LIVE når kamp pågår
2. Topp 5
3. Snakkiser
4. Min Lofthus
5. Mest populære

Den gamle store månedskolonnen er ikke tilbake. Topp 5 er full bredde og ligalederen har tydeligst visuell vekt.

### Nytt LIVE-senter
LIVE løfter spilleren som gjør størst faktisk utslag i Lofthus og kobler hendelsen til managerne som vinner/taper mest mot ligaens effektive eierskap.

### Redaksjonell Snakkiser-motor
`lro_newsroom.py` gir historier:
- nyhetsverdi
- ferskhet
- status
- confidence
- levetid
- persistence/hysteresis

Store historier blir ikke skjøvet ut av mindre statistikk. Live bevegelse omtales som foreløpig. En spiller som ennå ikke har spilt blir ikke stemplet som 0-poengsfiasko.

### Ligatabellen
Primærinformasjon:
- plass
- manager / lag
- kaptein
- GW
- total
- +/-

Klikk manager-navnet for meny:
- Se laget
- Sammenlign
- Rivalradar
- Historikk

På mobil reflower raden til en kompakt sportsrad i stedet for å presse desktop-tabellen inn på skjermen.

### Managerprofil V800
- kompakt profilheader
- visuelt lag på fotballbane
- spillerstatus: live / ferdig / ikke startet
- C / VC / TC
- live poeng
- kort live-fortelling
- kompakt Form
- progressive expanders for chips, karriere og meritter
- spillere er klikkbare

### Rivalradar
Rivalradar sammenligner to faktiske lag og viser:
- poenggap
- live GW
- spillere igjen
- kapteiner
- felles bidrag
- unike multiplier-forskjeller
- **Heia på**
- **Håp på blank**
- live swing per spiller

### Spillerprofiler
Klikk relevante spillere for å se:
- GW-poeng
- Lofthus-eierskap
- kapteiner
- effektivt eierskap
- status
- hvem som profiterer mest mot feltet
- eiere/kapteiner med managerlenker

### Hall of Fame
Hall of Fame er ryddet til fire hovedinnganger:
- Hall of Fame
- Mestere
- Månedsvinnere
- Rekorder

Historisk korreksjon i V800:
- **Rasmus Grytvik-Skoglund: 3. plass i 2024/25**

Korreksjonen fyller bare et manglende `third_place`-felt for 2024/25. Dersom den persistente CSV-en senere inneholder en eksplisitt annen verdi, overskriver ikke koden arkivet.

## Ny arkitektur

`app.py` er redusert til en tynn router/shell.

- `lro_config.py` – league/config/branding
- `lro_fpl.py` – rå FPL API + cache/resilience
- `lro_live.py` – LiveState og autoritative liveberegninger
- `lro_league.py` – league/form/month/profile helpers
- `lro_newsroom.py` – Snakkiser og redaksjonell prioritering
- `lro_rival.py` – head-to-head og live swing
- `lro_routes.py` – URL/deep links/browser navigation
- `lro_history.py` – historiske fakta og Hall of Fame
- `lro_archive.py` – snapshots
- `lro_odds.py` – eksisterende oddslogikk
- `lro_ui.py` – sentralt designsystem og UI-primitiver
- `lro_pages/home.py`
- `lro_pages/league.py`
- `lro_pages/manager.py`
- `lro_pages/rivalradar.py`
- `lro_pages/history.py`
- `lro_pages/player.py`

## Routing
V800 bruker ordentlige query-URL-er for sidene. Manager- og rival-lenker er vanlige browsernavigasjoner, slik at Back/Forward og deep links kan fungere uten den gamle iframe-løsningen.

Eksempler:
- `?page=Ligaen&view=Tabell`
- `?page=Manager&manager=123`
- `?page=Rivalradar&me=123&rival=456`
- `?page=Spiller&player=351`

`?debug=1` viser teknisk diagnose uten å legge debug-data i normal UI.

## Kommersielt klargjort
Kjernen er ikke lenger hardkodet til ett liganavn i produktlogikken. Følgende kan styres med miljøvariabler:

- `LRO_LEAGUE_ID`
- `LRO_LEAGUE_NAME`
- `LRO_SEASON`
- `LRO_DATA_DIR`
- `LRO_EXPECTED_MANAGERS`

Lofthus er fortsatt pilotkunden og historikk/Hall of Fame er Lofthus-spesifikk. Livekjernen, managerprofiler, ligatabell og Rivalradar er nå langt nærmere en senere multi-league-modell.

Ingen ekstern tracking eller betalingskode er lagt inn.

## Deploy
1. Ta backup av repoet.
2. Pakk ut `LRO_V800.zip`.
3. Kopier innholdet til repo-roten.
4. **Ikke slett eller overskriv din eksisterende `data/`-mappe.** V800-pakken leveres uten private/persistente datafiler.
5. Commit/push.
6. Render eller Streamlit Community Cloud kan starte `app.py` som før.

`render.yaml` og GitHub-arkivworkflowen fra den fungerende V706-linjen er bevart.

## Kjente begrensninger
- Build-containeren hadde ikke Streamlit installert og hadde ikke nettverk til å installere pakken. Derfor er ekte Streamlit browser-smoke-test merket **NOT RUN**, ikke PASS.
- Ekstern FPL HTTP-smoke-test kunne ikke kjøres i build-containeren.
- Faktisk 320/390/768/1024/1440 px browser-test kunne ikke kjøres her. Responsiv CSS er implementert, men må ses i deploy.
- FPL bestemmer når autosubs og endelige bonuspoeng publiseres. V800 refresher picks ved kampstatusoverganger og mellom kamper, men later ikke som foreløpige FPL-data er endelige.
