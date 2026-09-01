# Lofthus Road Open V605

V605 er en kompakt profil- og Spilleroversikt-oppdatering bygget på V604.

## Managerprofil
- Plass, poeng, GW-poeng og relevant månedsplass ligger nå inne i managerheaderen.
- Hvis en ny måned ennå ikke har fått poeng, brukes siste ferdige måned også på managerprofilen.
- Lofthus-meritter er fremhevet som en egen gullmarkert prestisjelinje.
- FPL-historikk ligger i en kompakt høyreboks med beste overall, høyeste sesongpoeng, antall tidligere sesonger og topp-100k-sesonger, samt de siste fem sesongene.
- Før-sesongodds for seriegull og topp 3 vises på profilen.
- Modellens liveodds for seriegull vises på profilen og caches per stilling/GW.
- Lagverdi og bank er fjernet.
- Det gamle ekstra odds-toggle-/analysefeltet er fjernet. Kun én tydelig vei videre til Rivalradar står igjen.

## Tropp
- Startelleveren beholdes på taktisk bane.
- Benken er flyttet inn i samme mørke troppsflate som resten av laget.
- Benkens poeng summeres direkte fra de fire benkespillerne. Dermed viser Bench Boost-runder den faktiske summen (f.eks. 11), ikke en misvisende 0 fra et annet API-felt.
- Formasjonsvisningen er komprimert for mindre scrolling.

## Spilleroversikt
- Standardsiden er kortet kraftig ned.
- Søk ligger først.
- Kapteiner, mest eide og differensialer vises side om side på desktop, topp 5 i hver.
- Full kapteinsoversikt finnes fortsatt, men ligger lukket i en expander til den faktisk trengs.
- Månedstabell og rundebevegelser er fjernet fra denne siden fordi de allerede finnes bedre plassert på Forsiden/Ligaen.
- Målet er svar på spiller-/kapteinsspørsmål uten en lang scroll-side.

## Beholdt
- V602 Hall of Fame-sortering.
- V603 avisforside.
- V604 bakgrunnslasting på forsiden.
- Pris-, chip-, kaptein- og historikklogikk.

## Deploy
Legg alle filene i denne mappen i repo-roten og overskriv filer med samme navn. Behold eksisterende `data/` urørt.
