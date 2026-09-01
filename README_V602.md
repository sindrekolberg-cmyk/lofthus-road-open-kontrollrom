# Lofthus Road Open V602

Hotfix/polish etter V601.

## Endret
- Hall of Fame-rangeringen er korrigert.
  - Sesongtitler er alltid øverste kriterium.
  - Ved likt antall sesongtitler brukes olympisk prinsipp på øvrige meritter: gull først, deretter sølv, deretter bronse.
  - Cupgull + månedsseire teller derfor før andre-/tredjeplasser.
- Samme sorteringslogikk ligger både i `lro_history.py` og som bakoverkompatibel fallback i `app.py`.
- Teksten under Hall of Fame forklarer den faktiske regelen.
- Forsidens store hero er kraftig komprimert:
  - lavere høyde
  - mindre ligaleder-typografi
  - siste runde og månedsstatus ligger ved siden av hverandre
  - beholder én samlet redaksjonell flate, men uten å dominere hele skjermen
- Mobilvarianten er også komprimert.

## Deploy
Last opp alle filene i denne mappen til repo-roten og overskriv filene med samme navn.
Behold eksisterende `data/` urørt.
