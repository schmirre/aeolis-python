# AeoLiS Studio

Ett webbgränssnitt för 1D-körningar med AeoLiS. Appen skapar indatafiler, kör det vanliga kommandot `aeolis run` och visar resultatet. Själva modellkoden ändras inte.

Du kan:

1. ladda upp uppmätta profiler före och efter, med datum i filnamnet,
2. ladda upp vind, vattenstånd och (valfritt) vågor och kornfördelning,
3. ställa in kustens orientering, sediment, vegetation och processer,
4. köra modellen och se profiler, volymer och transport,
5. jämföra med den uppmätta profilen efter (RMSE, Brier skill score, volym per zon),
6. kalibrera Cb och T mot mätningen,
7. jämföra flera körningar sida vid sida.

## Starta i GitHub Codespaces (inget att installera)

**En gång:** öppna terminalen i ditt codespace och kör

```
bash tools/aeolis_studio/install.sh
```

**Sedan, varje gång:** öppna en ny terminal och skriv

```
aeolis-studio
```

Första starten skapar Python-miljön och installerar AeoLiS och appen (några minuter). Därefter startar appen på några sekunder. En ruta nere till höger erbjuder att öppna den i webbläsaren. Ser du ingen ruta: fliken **Ports**, jordgloben vid port 8501. Stoppa appen med Ctrl+C.

Kommandot fungerar både i repots standardkonfiguration (conda, där miljön `aeolis` med Python 3.12 skapas automatiskt) och i konfigurationen **AeoLiS Studio** (där allt redan är installerat och appen startar av sig själv).

Stäng av codespacet när du är klar (**Code → Codespaces → ⋯ → Stop codespace**) så att din gratiskvot räcker längre. Filer, körningar och kommandot finns kvar tills codespacet tas bort.

## Starta på egen dator (Linux eller macOS)

```
bash tools/aeolis_studio/install.sh
aeolis-studio
```

## Filformat

Alla tider i UTC och alla höjder i RH2000. Komma eller semikolon som avgränsare går bra.

| Fil | Kolumner | Kommentar |
| --- | --- | --- |
| `profil_2023-04-12.csv` | `x_m, z_m` | Mätdatum i filnamnet. x från en fast referenspunkt, ökande mot land |
| vind | `time_utc, speed_ms, dir_deg` | Riktning varifrån vinden blåser, 0 = nord |
| vattenstånd | `time_utc, wl_m` | |
| vågor (valfri) | `time_utc, hs_m, tp_s` | Utan fil används en konstant våghöjd |
| sediment (valfri) | `d_mm, mass_pct` | Kornklasser och massprocent. Utan fil används d50 |

Tid skrivs som `2023-04-12T13:00`. Tidsserierna måste täcka hela perioden mellan profilerna.

Exempel finns i `exempeldata/`: vind från Europlatform, vattenstånd från Hoek van Holland och vågor för februari till april 2012 (från AeoLiS egna exempel), en syntetisk startprofil och en syntetisk "uppmätt" profil efter. Den senare är skapad med Cb = 2,2 och T = 3 s, så en kalibrering bör hitta värden i närheten.

## Var dina filer hamnar

Allt sparas i `tools/aeolis_studio/projekt/`:

- `indata/` uppladdade filer
- `korningar/` en mapp per körning med `aeolis.txt`, alla indatafiler och `aeolis.nc`
- `kalibreringar/` en mapp per kalibrering med en undermapp per prov och `results.csv`

Mappen `projekt/` ignoreras av git, så dina data följer inte med om du committar. Varje körningsmapp kan köras om utan appen med `aeolis run aeolis.txt`.

## Kommandorad

Samma funktioner finns utan gränssnitt:

```
python -m studio bygg      exempeldata/scenario.json projekt/korningar/test
python -m studio kor       projekt/korningar/test
python -m studio jamfor    projekt/korningar/test --scenario exempeldata/scenario.json
python -m studio kalibrera exempeldata/scenario.json projekt/kalibreringar/test --n 24 --mal volym --zon Dyn
```

Sökvägar i `scenario.json` räknas från mappen du står i.

## Att tänka på

- **Kustnormal** är riktningen som pålandsvinden kommer från, till exempel 270° för en västvänd kust. Vinden vrids mot profilen med den.
- **Fukt** är påslaget som standard. Utan fukt påverkar vågorna ingenting.
- **Återställ våt bädd** drar tillbaka bottnen mot startprofilen där vattnet når upp. Använd den för långa perioder, annars grävs strandplanet ur eftersom AeoLiS inte räknar marin återfyllnad.
- **Kalibrering**: om flera kombinationer av Cb och T ger nästan samma poäng kompenserar parametrarna varandra. Kontrollera då mot en andra mätperiod innan du väljer värden.
- Rapporterna (knapparna "Ladda ner rapport") är korta markdown-filer som går att klistra in i en chatt med Claude för tolkning.
