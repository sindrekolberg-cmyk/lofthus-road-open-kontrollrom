# Lofthus Road Open V821 · IMAGE PIPELINE HOTFIX

V821 bygger direkte på V820 SPORTSFRONT. Endringen er målrettet: V820 rendret riktige `<img>`-elementer, men spillerbildene ble hotlinket direkte fra Premier League-CDN-en i brukerens nettleser. På den deployede Streamlit-siden feilet disse kallene, slik at heroen og spillerkortene ble stående tomme.

## Endret

- Premier League-spillerbilder hentes nå **server-side** av Streamlit og embeds som data-URI.
- Bildene caches i 6 timer, så siden skal ikke laste samme bilde på nytt ved hver rerun.
- Resolveren prøver flere PL-størrelser/namespaces og legacy-path før den gir opp.
- Dersom alle bildekilder feiler, returneres ingen `<img>` og de eksisterende tekst/initial-fallbackene kan brukes i stedet for et usynlig ødelagt bilde.
- Samme resolver brukes i SPORTSFRONT, Snakkiser, populære spillere, spillerprofiler og managerens lagoppstilling.
- Ingen live-, ranking-, historikk- eller Rivalradar-logikk er endret.

## Viktig

V821 er en teknisk bilde-hotfix. Selve SPORTSFRONT-layouten fra V820 er beholdt.

For senere kommersiell bruk må rettighetene til Premier League-spillerbilder avklares; denne hotfixen løser leveringsteknikken, ikke lisensiering.

- Den offentlige dashboard-stripen «Leder / Forrige GW / Måned» over hovedsaken er fjernet. Topp 5 og Snakkiser bærer denne konteksten i stedet.
