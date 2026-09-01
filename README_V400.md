# Lofthus Road Open V400 – The Rebuild

V400 er en kontrollert rebuild av V301. Den gamle 7.500-linjers `app.py` er ikke videreført som et nytt lag. Frontend, dataflyt, Rivalradar, odds og historikk er skilt i noen få tydelige moduler.

## Deploy i GitHub

Behold den eksisterende `data/`-mappen urørt.

Last opp disse seks filene til **roten av repoet** og erstatt eksisterende `app.py`:

- `app.py`
- `lro_fpl.py`
- `lro_analysis.py`
- `lro_history.py`
- `lro_odds.py`
- `lro_ui.py`

`requirements.txt` kan også erstattes med filen i pakken, men dagens requirements kan stå dersom den allerede har Streamlit, pandas og requests.

Ikke last opp `tests_v400.py` eller test-rapporten til produksjon med mindre du vil ha dem i repoet som dokumentasjon.

## Hva som er bygget om

- Én autoritativ spillerpris: `bootstrap-static.elements[].now_cost / 10`.
- Kjøpspris og salgspris holdes separat fra markedspris.
- Managerprofil: form og meritter før troppen, posisjon + pris + C/VC/TC på spillerlinjen.
- Flermannssammenligning: 2–8 managere, liga/måned/GW.
- Rivalradar 2.0: henter bare deg + valgte rivaler først, og analyserer program, form, minutter, xGI, pris, rival-eierskap, budsjett og risiko.
- Transferforslag bruker salgspris ut og markedspris inn når salgspris finnes.
- Maks tre spillere fra samme klubb og samme posisjon valideres.
- Oddsmodell: historikk er viktig tidlig, men tones eksplisitt ned gjennom sesongen.
- Hall of Fame: olympisk sortering, gull → sølv → bronse.
- Ny måned vises som live med alfabetisk topp tre på 0 før poeng er registrert.
- Ingen gammel sidebar/debugstøy i normal brukerflate.
- Ingen gammel V100/V200/V300-frontend er kopiert inn.

## Viktig om estimater

Rivalradarens spillerutsikter og odds er beslutningsstøtte, ikke fasit. De er regel- og datadrevne og viser brede intervaller/enkle prosentanslag i stedet for falsk presisjon.

## Persistens

Streamlit Community Cloud gir ikke et sikkert permanent lokalt filsystem. Historikk fra `data/` er trygg, og inneværende sesong kan rekonstrueres fra FPL mens dataene er tilgjengelige. V400 later derfor ikke som at runtime-filer er et permanent arkiv.
