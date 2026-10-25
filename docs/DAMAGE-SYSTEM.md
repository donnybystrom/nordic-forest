# Skadesystemets första prototyp

Slå på **Meshskador och muskelförlust** i FPS-menyn. **1** väljer pistol, **2** en .44-spelprofil, **3** åtta hagel och **4** automateld när vänster musknapp hålls in. Alla använder tills vidare samma prototypvapen och magasin med 12 skott. Reglaget **Vävnadsförlust** ändrar geometri-/muskelverkan; **Total skottimpuls** ändrar den tidigare fysiska knuffen separat. Avstängda nya skador återställer inte redan skadade kroppar; **Spawna om grupp** gör det.

## Energi, vävnad och funktion

`damage_model.gd` använder en justerbar spelmodell:

```
E = 0,5 × projektilmassa × hastighet²
E_avsatt = E × profilens avsättningsandel
volymbudget_cm³ = E_avsatt / 2,5 × vävnadsmultiplikator
kanalradie = sqrt(volymbudget_m³ / (pi × kanallängd))
```

Massor, hastigheter, avsättningsandelar och särskilt **2,5 J/cm³ är författade spelparametrar**, inte en kalibrerad sårballistisk funktion. Kanallängden uppskattas från nästa intakta meshskärning, med en reservlängd när ingen utgång hittas. Cellens borttagna volym uppskattas som ursprunglig ytarea × 24 mm skaltjocklek. Hela celler väljs inom budgeten; upplösningen kan därför ge mindre vävnadsförlust än budgeten. HUD:s cm³ är denna modelluppskattning.

| Spelprofil | Energi per projektil | Avsatt andel | Förstärkt totalimpuls |
| --- | ---: | ---: | ---: |
| Pistol, 8 g / 350 m/s | 490 J | 38 % | 14 N s |
| .44, 15,6 g / 420 m/s | 1 375,92 J | 65 % | 70 N s |
| Hagel, 8 × 3,5 g / 360 m/s | 226,8 J per hagel | 65 % | 100 N s, delat på 8 |
| Automateld, 4 g / 800 m/s | 1 280 J | 42 % | 18 N s, nominellt 10 skott/s |

Den tidigare punktimpulsen tillämpas en gång vid träffen. Skadearbetet väntar två fysiksteg, så att impulsen hinner spridas genom den ledade kroppen före eventuell avskiljning. Fragment ärver aktuell punkt- och vinkelhastighet. Deras begränsade extra utkast ger en motimpuls på ursprungskroppen. Borttagen uppskattad massa dras från dess fysikkropp.

Muskelhälsa och avskiljning är separata: `max(0, 1 − 4 × regional volymförlust)` ger en period med obrukbar men fortsatt fäst lem. Vid 48 % regional förlust frigörs lemmen vid sin befintliga led, inklusive underliggande delar. Det är en grov regional integritetsregel, **inte en löst geometrisk ben-/senbrottsyta**. Avskilda delar använder de befintliga fysikkropparna och nedströmslederna. Inkommande led, motorer och stöd tas bort; masscentrum räknas om och kvarvarande hudvikter kopplas bort från den avskilda grenen.

Huvudet har dessutom en enkel ellipsoid som hjärnproxy med en ackumulerad speltröskel på 400 avsatta joule längs kanaler som korsar den. En kraftig central huvudträff eller avskilt huvud stoppar alla motorer, stöd, animation och återhämtning. Bröstskador har ingen generell HP-dödsregel. Ett skadat men fungerande bröst kan fortfarande resa sig; skadade/avskilda ben växlar referensen till krypning. Fotarbete och skadespecifika uppresningar behöver fortsatt utveckling.

## Geometrin och kostnadstaken

`bake_damage.gd` körs före export och i den lokala Godot-startfilen. Den delar den befintliga ytan mellan deterministiskt jitterade Voronoi-frön, begränsat av anatomisk region från hudvikterna: **1 532 celler för kvinnan och 2 383 för mannen**. Trianglarna behålls hela. Detta är en ytcellsapproximation på befintlig triangulering, inte en fullständig polyedrisk Voronoi-uppdelning av en solid kropp.

Friska instanser delar den ursprungliga GLB:n. Vid skada får instansen ett eget yttre indexbuffer. Borttagna cellers trianglar kollapsas till noll area genom små indexuppdateringar. En kompakt, skinnad inneryta och sårkant byggs enbart kring såren. Det ger faktisk ändring av rendergeometrin, utan en alfamask. Strålar förfinas mot de aktuellt deformerade, intakta trianglarna och kan passera genom befintliga hål. En ny kula stannar vid första intakta ytan; återstående projektilenergi genom flera kroppar simuleras ännu inte.

De största lossnade cellerna bakas till texturerade, slutna skalfragment i den verkliga fysikposen. Högst **4 fragment per skadeomgång och 32 totalt** får egna kroppar; mindre överflödiga celler försvinner utan separata fysikfragment. Fragment lever sju sekunder och kolliderar med banan. Småfragment kastar inga skuggor. Deras kollisionsform är en liten sfär; karaktären använder fortsatt förenklade kapslar. Avskilda större lemmar behåller sina ledade kroppar och lever till nästa respawn. Flera hagel som når samma agent i samma fysiksteg delar en geometriuppdatering.

Godot 4.7:s [RenderingServer-indexuppdatering](https://docs.godotengine.org/en/stable/classes/class_renderingserver.html#class-renderingserver-method-mesh-surface-update-index-region) används för den yttre ytan. Hudvikter, cellgrannar och viktindex bakas i förväg. Ingen boolesk helmeshoperation, Delaunay-beräkning eller GPU-läsning behövs per kula. GLB-filer, animationer och originaltexturer ändras inte. De komprimerade `.dbin`-filerna genereras under ignorerade `build/` och följer med exporten, utan nya stora Git-filer.

## Verifiering och kvarstående gräns

`damage_smoke.gd` provar båda modellerna: energibudget, verkliga indexändringar med riktig renderare, hålstrålar, kort stråle till hud framför träffkapseln, huvudkollaps, samlade hagel, avslitna armar/underarmar/händer/lår/underben/fötter/huvuden, muskelbortfall med kvarvarande led, energistyrd avskiljning, skadad bröstkorg som reser sig efter en faktisk hagelavfyrning, 12 zombier under 72 begärda avfyrningar samt städning. Rapporten skiljer begärda avfyrningar från faktiska kroppsträffar. Godots headless-renderare verifierar inte GPU-indexändringen; den kontrollen körs bara med riktig rendering.

```sh
python3 tools/build_character_web.py
godot --headless --path build/character-web/project --fixed-fps 120 --script res://testground/damage_smoke.gd --log-file /tmp/damage-physics.log
godot --path build/character-web/project --fixed-fps 120 --script res://testground/damage_smoke.gd --log-file /tmp/damage-render.log
godot --path build/character-web/project --disable-vsync --script res://testground/damage_benchmark.gd --log-file /tmp/damage-benchmark.log
node tools/test_testground_web.cjs --channel chrome
```

Rapporter ligger i `build/character-web/damage-validation.json` och `damage-benchmark.json`; renderbilder i `build/character-web/verification/damage/`. Browserprovet använder riktiga mus-/tangentbordshändelser och verifierar även hållen automateld. `--damage-only` hoppar över de äldre kontroll-/uppresningsfallen för snabb lokal felsökning. CI kör hela browserprovet och de separata fysikregressionerna före Pages-publicering.

Skalmodellen ger en första mätbar grund. Solid volymvävnad, modellerade ben/senor, fyllda anatomiska stumpar, godtyckliga snitt mitt på ben, exakt korssnittsintegritet och mjuk vävnadsdeformation återstår. Kostnadstaken hindrar okontrollerad fragmenttillväxt, men innebär ingen garanti om en viss FPS på alla webbläsare eller mobiler. Använd den separata realtidsmätningen för bildfrekvens; ett headless-test med fast simulerad takt är ingen FPS-mätning.

### Lokalt realtidsprov 2026-10-25

Apple M1 Pro, Godot 4.7.1 Compatibility/OpenGL, andra projekt öppna samtidigt. Tolv zombier/204 ledade kroppar: en tre sekunders referensperiod gav 54,2 FPS i medel. Sex sekunder med nominell automateld gav 25,5 FPS; 61 avfyrningar, 18 faktiska kroppsträffar, maximalt 32 småfragment. Bildrutornas 95:e percentil under eld var 60,8 ms, den långsammaste 179,3 ms. Detta visar en kvarstående kostnad vid belastning; prototypen har ingen godkänd 60-FPS-nivå för tolv skadade zombier. Mätningen är ett kort lokalt prov, inte ett generellt maskinresultat eller en browsermätning.
