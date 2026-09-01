# Lofthus Road Open V500 — My Lofthus

V500 er den store produkt- og designoppgraderingen bygget videre på V407.

## Viktigste endringer

- Ny visuell identitet: mørk stadion-/flomlys-følelse, varmere kremflater, gullaksenter, sterkere typografi og mindre «standard Streamlit».
- Forsiden er bygget om som en sportsforside med stort hovedoppslag, siste rundevinner og månedskamp.
- Ny **Mitt Lofthus**-del: velg deg selv én gang i økten og få avstander, nærmeste rival og viktige forskjeller. Ett klikk åpner Rivalradar med managerne rundt deg ferdig valgt.
- Snakkiser vises som redaksjonelle høydepunkter, maks fire.
- Kapteinsoversikten er en interaktiv todelt flate: klikk på spiller til venstre, få alle kapteiner/TC-er til høyre. På mobil stables den.
- Rivalradar viser navnene på rivalene som har eller mangler anbefalte spillere.
- Liga-tabellen har samme visuelle språk som resten og beholder klikk-sortering direkte på kolonneoverskriftene.
- **Odds før sesongstart** ligger under Ligaen og er skjermet mot 2026/27-resultater, slik at markedet ikke omskriver historien.
- Hall of Fame har fått podium-/museumspreg. Sesongtitler er fortsatt øverste rangeringskriterium.
- Sesongarkivet bruker samme sportslige listeuttrykk som resten av siden.
- Mesterrekorder er defensivt sikret mot gammel cache/HistoryStore og skal falle tilbake pent i stedet for å vise rød app-feil.
- Språkpolish: «poeng», riktig entall/flertall for «månedsseier», «Månedskonger» som kategorinavn.

## Navigasjon

- Forside
- Ligaen
  - Tabell
  - Manager
  - Sammenlign
  - Odds før sesongstart
- Rivalradar
  - Rivaler
  - Spilleroversikt
- Hall of Fame
  - Rangering
  - Månedskonger
  - Sesonger
  - Rekorder

`Odds` er med vilje **ikke** en egen Rivalradar-fane. Den siste produktbeslutningen var å ha før-sesongoddsen under Ligaen, mens løpende modellanslag bare vises i konkrete analyser/sammenligninger.

## Deploy

Legg disse filene i roten av GitHub-repoet og overskriv eksisterende filer:

- `app.py`
- `lro_fpl.py`
- `lro_analysis.py`
- `lro_history.py`
- `lro_odds.py`
- `lro_ui.py`
- `requirements.txt`

Behold eksisterende `data/` urørt. V500-pakken inneholder derfor ikke en ny `data/`-mappe.
