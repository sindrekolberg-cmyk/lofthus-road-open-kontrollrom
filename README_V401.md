# Lofthus Road Open V401

V401 er en kvalitets- og UX-pass på V400. Målet er mindre støy, tydeligere hierarki og mer korrekt sportslogikk uten å bygge nye hovedområder.

## Viktigste endringer

- Hall of Fame rangeres nå først etter sesongtitler. Deretter teller cupgull, månedsseire og øvrige pallplasser.
- Hall of Fame viser merittenes type i stedet for å slå alle gull sammen til én misvisende gullsum.
- Den separate Triple Captain-varselboksen er fjernet. TC vises i selve spiller-/kapteinslinjen, med manageren markert `(TC)`.
- Ligatabellen viser chip brukt i aktuell GW under lagnavnet, uten en ny kolonne. Triple Captain viser også valgt spiller.
- Ligatabellen kan sorteres på `Tabellen`, `Mest opp`, `Mest ned` og `Beste GW`. Den faktiske ligaplasseringen beholdes i første kolonne uansett sortering.
- Dersom runden pågår, markeres tabellen diskret som live.
- Managerprofilen viser chiphistorikk kompakt, og viser bare current-GW-chip som egen status når en chip faktisk er aktiv.
- Rivalradaren er strammet inn: `Dekk deg`, `Behold`, `Hent`, maks tre treff per blokk, maks tre transferforslag.
- `Hva om?` og odds er flyttet inn under `Mer analyse`, slik at hovedvisningen holder seg ren.
- `Din situasjon` erstatter mer knotete strategi-språk.

## Deploy

Behold eksisterende `data/`-mappe i GitHub.

Last opp filene fra denne mappen til repo-roten og erstatt de eksisterende V400-filene:

- `app.py`
- `lro_fpl.py`
- `lro_analysis.py`
- `lro_history.py`
- `lro_odds.py`
- `lro_ui.py`

`requirements.txt` kan også lastes opp, men inneholder ingen nye avhengigheter sammenlignet med V400.
