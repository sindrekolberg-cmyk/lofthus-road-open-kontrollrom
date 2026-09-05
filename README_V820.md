# Lofthus Road Open V820 · SPORTSFRONT

V820 bygger direkte på V810/V801-motoren, men forkaster V810 som designretning.
Målet er enkelt: **sportsnettsted først, analyseverktøy ett nivå ned**.

## Hva som er endret

- Forsiden er komponert som en sportsfront, ikke som et dashboard.
- LIVE har én tydelig hovedhistorie med stor spillerflate, kampstatus og en kort redaksjonell forklaring.
- Topp 5 er integrert som en egen standings-rail ved siden av hovedhistorien på desktop.
- De tre gamle statuskortene er erstattet av en liten kontekstticker.
- Snakkiser viser én stor hovedsak og to sekundærsaker med ulik visuell behandling.
  - spillerhistorier bruker spillerbilde
  - store plassendringer får egen grafisk behandling (pil + antall plasser)
  - måned/rundevinner har egne visuelle varianter
- «Mest populære» er erstattet av image-first spillerkort: spiller, klubb, eierskap og kapteinandel.
- «Min Lofthus» er redusert til en rolig personlig stripe når identitet er valgt.
- Rivalradar/EO/chips/sammenligning m.m. er beholdt, men presenteres som et frivillig analyselag.
- Forsiden viser maksimalt tre Snakkiser.

## Spillerbilder

V810 brukte den gamle Premier League-stien:

`/premierleague/photos/players/250x250/p{id}.png`

Det var årsaken til de store tomme bildeflatene i V810.

V820 bruker FPL-feltet `photo` og dagens Premier League asset-tre:

`/premierleague25/photos/players/500x500/{photo_id}.png`

med automatisk fallback til 250x250 hvis den store cutouten mangler.
Dette brukes i LIVE, Snakkiser, spillerkort, spillerprofil og lagoppstilling via den samme katalogen.

## Det som IKKE er bygget om

- LiveState / én live-sannhet
- kaptein / TC / Bench Boost / hits
- månedstabell og månedspoeng
- newsroom persistence og redaksjonelle regler
- managerprofil
- Rivalradar
- browser Back/Forward og deep links
- historikk / Hall of Fame
- Rasmus Grytvik-Skoglund som 3. plass i 2024/25

## Filer med hovedendringer

- `lro_pages/home.py` – ny redaksjonell frontside
- `lro_ui.py` – V820 SPORTSFRONT designsystem og nye komponenter
- `lro_fpl.py` – korrigert spillerbildesti
- `app.py` – V820-versjon

## Deploy

Pakk ut innholdet i repo-roten og deploy som før.
Ikke erstatt en eventuell eksisterende `data/`-mappe med gamle data.

Ingen nye Python-avhengigheter er lagt til.

## Begrensninger i denne byggjobben

Streamlit er ikke installert i byggcontaineren, så full runtime-/browser-smoke mot live FPL-data kunne ikke kjøres her. Python-kompilering og 11 automatiserte core/integrasjonstester er kjørt. En separat statisk 1440px designmock ble også rendret under utviklingen for å kontrollere komposisjonen før koden ble pakket.
