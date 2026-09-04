# Lofthus Road Open V704 – Manager Menu

Denne versjonen bygger direkte på den ekte V702-pakken.

## Endret
- Den store «September · live»-kolonnen er fjernet fra forsiden. Månedens leder lever fortsatt i status/headline-laget, men forsiden bruker ikke en hel ekstra tabellkolonne på det.
- Forsidens Topp 5 står nå alene og får mer ro.
- Ligatabellen viser kaptein for hver manager direkte: `Haaland (C)` / `Haaland (TC)`.
- Chipbruk vises fortsatt diskret under lagnavnet.
- Manager-navn i ligatabellen er nå ekte Streamlit-popover-menyer, ikke en iframe-lenke som kan dø i nettleserens sandbox.
- Klikk på navn åpner en meny med «Se laget» og «Sammenlign».
- «Se laget» går direkte til riktig managerprofil og tropp.
- «Sammenlign» tar manageren med inn i sammenligningsvisningen.

## Deploy
Legg alle filene i denne mappen i repo-roten og overskriv filer med samme navn.
Behold eksisterende `data/` urørt.
