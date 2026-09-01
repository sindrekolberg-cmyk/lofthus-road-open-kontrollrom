# Lofthus Road Open V600

## The Editorial / My Lofthus Update

V600 bygger videre på V500, men går bevisst bort fra kort-grid/dashboard-estetikken. Målet er mer redaksjonell sportsflate, mindre UI-støy og mer personlig analyse.

### Viktigste endringer

- Snakkiser er nå en redaksjonell liste, ikke fire kort.
- Hall of Fame er én sammenhengende liste. Topp 3 fremheves i samme struktur i stedet for egne podiumkort.
- Hall of Fame bruker én felles sorteringslogikk: sesongtitler først, deretter sammenlagtpaller, cup og månedsmeritter.
- Forsiden beholder den brede redaksjonelle hero-komposisjonen og de kompakte Topp 5/måned-listene.
- Mitt Lofthus er flatere og mindre kortpreget, og foreslår automatisk relevante rivaler rundt valgt manager.
- Rivalradar forhåndsvelger relevante managere foran/bak deg og månedskonkurrenter når måneden har reelle poeng.
- Rivalanalysen viser navn på hvem som eier/mangler spillerne og hvem av rivalene som faktisk har dem som kaptein denne runden.
- Transferforslag vises som faktiske bytter med salgspris, innpris og penger igjen.
- Spilleroversikten starter med ett spillersøk. Spillerprofilen viser både Lofthus-eierskap og FPL-eierskap.
- Kapteinsoversikten beholder todelt desktop-layout med spillerliste til venstre og full detalj til høyre.
- Manager i ligatabellen er klikkbar og kan åpne managerprofilen direkte.
- Meritter ligger høyere enn form på managerprofilen.
- Før-sesongodds kan fryses til `data/preseason_odds_2026_27.csv` og overskrives aldri automatisk.
- Ny `lro_archive.py` lager repo-vennlige, atomiske GW-snapshots og sesongfinale når full ligadata er lastet etter en ferdig GW.
- Snakkiser om tabellbevegelse sier eksplisitt «forrige runde».
- Current market price er fortsatt `now_cost / 10`; salgspris brukes bare i transferbudsjett.

### Historikkarkiv

V600 kan skrive snapshots til `data/snapshots/` dersom filsystemet er skrivbart. Dette er et stabilt JSON-format som kan legges i Git-repoet og dermed overleve FPLs sesongreset.

Viktig: Streamlit Community Cloud skriver ikke automatisk tilbake til GitHub. Filer som kun oppstår på Cloud-instansen er derfor ikke permanente gjennom en ny deploy. V600 gjør selve arkivformatet og snapshot-genereringen klar og feil-tolerant; permanent automatisk GitHub-synk kan kobles på senere med en eksplisitt write-token/lagringsløsning.

### Deploy

Last opp hele innholdet i denne mappen til repo-roten og overskriv eksisterende app-/modulfiler.

**Behold eksisterende `data/` urørt.** V600-pakken inneholder med vilje ingen `data/`-mappe.

Entry point er fortsatt `app.py`.

### Filer

- `app.py`
- `lro_ui.py`
- `lro_analysis.py`
- `lro_fpl.py`
- `lro_history.py`
- `lro_odds.py`
- `lro_archive.py`
- `requirements.txt`
- `README_V600.md`
- `V600_TEST_REPORT.txt`

### Testing

Se `V600_TEST_REPORT.txt`.
