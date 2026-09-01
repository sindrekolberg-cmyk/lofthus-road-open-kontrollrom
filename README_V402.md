# Lofthus Road Open V402

V402 er en målrettet tabell-hotfix på V401.

## Endringer
- Fjernet egen «Sorter»-velger over ligatabellen.
- Ligatabellen bruker nå en native sorterbar tabell: klikk direkte på `+/-` for å sortere størst opp / størst ned.
- `#` viser alltid faktisk ligaplassering, også når tabellen sorteres på andre kolonner.
- Lagnavn er tilbake som vanlig tekst, ikke Python-dict.
- Chipbruk vises diskret i Lag-feltet, f.eks. `Bassen Går · Bench Boost`.
- Sortering skjer lokalt i tabellen og utløser ikke nye FPL-kall.

## Deploy
Hvis V401 allerede ligger ute, holder det å erstatte `app.py` med V402-versjonen. Resten av V401-modulene er kompatible.

Behold eksisterende `data/` urørt.
