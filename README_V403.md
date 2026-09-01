# Lofthus Road Open V403

Kvalitetsoppdatering på V402.

## Endret
- Forsiden viser **Topp 5** og **månedstabellen** side om side på desktop. De stables automatisk på mobil.
- Hovedmenyen er redusert til **Forside · Ligaen · Rivalradar · Historikk**.
- **Sesong** ligger nå inne i Rivalradar sammen med **Rivaler** og **Odds**.
- Den gamle før-sesong-oddstabellen er tilbake. Den bruker bare tidligere FPL-sesonger og LRO-meritter, slik at 2026/27-poeng ikke omskriver før-sesongmarkedet.
- Odds-siden viser også et separat, løpende **Akkurat nå**-anslag.
- Historikk → Rekorder har fått **Mesterrekorder** basert på registrerte LRO-vinnere.
- Øyvind Nordmo Sivertsens dokumenterte FPL-historikk fra 2020/21–2025/26 er lagt inn som kildebelagt alumni-historikk.
- Mesterrekordene kan hente FPL Previous Seasons automatisk for dagens managere og bruke den statiske Nordmo-historikken når han ikke finnes i årets liga.

## Deploy
Legg filene i repo-roten ved siden av eksisterende `data/`.

**Ikke slett eller overskriv `data/`-mappen.**

Streamlit-entrypoint er fortsatt `app.py`.
