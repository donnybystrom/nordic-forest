# Karaktärer och gemensamma animationer i Godot

Granskaren innehåller strandzombien med 52 ben och strandturisten med 22 ben. Båda har samma 13 animationsklipp. Sedan 2026-10-23 finns även en första active-ragdoll-prototyp med dragbar boll och justerbart höftstöd. Självbärande balans, fotplacering och fot-IK återstår.

Starta genom att dubbelklicka på `tools/open_character_review.command`. Den tidigare startfilen `tools/zombie_beach/open_rodin_tpose_review.command` öppnar samma utbyggda scen. Projektet ligger kvar i `output/zombie-beach/rodin-tpose-v1/godot-review/project.godot`.

| Kontroll | Funktion |
| --- | --- |
| Modellmeny, pilar eller Q/E | Föregående/nästa karaktär |
| Klippmeny, pilar eller vänster/höger | Föregående/nästa animation, inklusive vilopose |
| Pausa/spela eller mellanslag | Pausa och fortsätt animationen; fysiken fortsätter |
| Tidsreglage | Sök i klippet, även när det är pausat |
| Hastighet | 0,1–1,5 gånger originalhastigheten |
| Dra orange boll | Flytta bollen med en kraftfjäder och putta kroppen |
| Dra bakgrund / mushjul | Rotera / zooma |
| R / B | Återställ kropp / hämta bollen |

Modellbyte behåller klipp, relativ tidpunkt, hastighet och pausstatus när klippet finns på båda. Viloposen bevaras också vid byte. Saknas ett valt klipp på en framtida modell väljs dess första tillgängliga klipp. UUID-namngivna källklipp får en kort källidentifierare i menyn; hela namnet visas i verktygstipset.

## Fysiklabb med dragbar boll

Startfilen öppnar nu **Aktiv fysik**. I Godot-editorn kan läget väljas i menyn under animationens tidsreglage. **Animation** visar originalrörelsen utan fysikkroppar. **Aktiv fysik** låter kroppen försöka följa animationen med begränsade vridmoment. **Slapp ragdoll** stänger av både motorerna och höftstödet, så kroppen faller och reagerar på kontakt.

Bollen har riktig massa och kolliderar med kroppen och golvet. Vänsterdra den mot karaktären; **Testknuff** skjuter den mot kroppen med 6 m/s. Dragningen använder en fjäderkraft med begränsad styrka, inte en förflyttning av kroppens transform. När musen släpps behåller bollen sin rörelse. **Hämta bollen** placerar den på skärmens vänstra sida om kroppen. Ett tappat fönsterfokus släpper dragningen.

| Reglage | Betydelse |
| --- | --- |
| Muskelkraft | Styrkan i posföljningen, 0–1,5 |
| Balanshjälp | Styrkan i ett virtuellt höftstöd, 0–1 |
| Boll kg | Bollens massa, 1–20 kg |
| Visa kollisionskroppar | Visar de förenklade fysiska formerna |
| Återställ kropp | Återställ till den aktuella animationsposen och hämta bollen |

Balanshjälpen är en begränsad fjäderkraft vid höften och kan hålla kroppen uppe även utan realistisk fotkontakt. Den är ett provverktyg för kontakt och posföljning. När balanshjälpen dras till noll måste kroppen bära sig mot golvet; prototypen kan då falla. En kommande balanskontroller behöver fördela vikten över fötterna, hantera stödytan och ta återhämtningssteg.

Varje karaktär har 17 `RigidBody3D`-kroppar och 16 `Generic6DOFJoint3D`-leder. Jolt körs vid 120 fysiksteg per sekund med 48 hastighets- och 16 positionsiterationer. Posmotorerna använder kropparnas tröghetstensorer, dämpning och begränsade vridmoment. En dold animationsreferens tillhandahåller målposen; `SkeletonModifier3D` för över den simulerade posen till den synliga meshen efter animationsutvärderingen. Kropparnas transform sätts när ett prov återställs, medan löpande rörelse sköts av fysiken.

Kvinnans simulerade massa är satt till 65 kg och mannens till 95 kg i katalogen. Det är valda provvärden, inte uppmätta kroppsmassor. Fördelningen mellan kroppsdelar och kapslarnas radier är förenklade. Delar längre än två leder från varandra kan kollidera; närliggande former har undantag för att undvika överlapp kring lederna. De breda vinkelgränserna behöver anatomisk finjustering. Fingrar och tår saknar egna fysikkroppar.

I fysikläget hålls animationens horisontella rotförflyttning på plats så att gångloopar fungerar i samma provyta. Kroppen kan fortfarande förskjutas av kollisioner; höftstödet försöker föra tillbaka den. Animationens vertikala rörelser och rotationer finns kvar som mål. Byte av modell, klipp eller tidsposition återställer fysikposen. Muskelkraft, balanshjälp, bollmassa och visning av kollisionskroppar följer med vid modellbyte.

`integrations/godot/character-review/active_ragdoll.gd` innehåller fysiken och `physical_pose.gd` överför resultatet till skelettet. Godots dokumentation beskriver [RigidBody3D-krafter](https://docs.godotengine.org/en/stable/classes/class_rigidbody3d.html), [ledbegränsningarna](https://docs.godotengine.org/en/stable/classes/class_generic6dofjoint3d.html) och [modifierarnas ordning efter animation](https://docs.godotengine.org/en/stable/classes/class_skeletonmodifier3d.html).

### Fysikprov

`physics_smoke.gd` provar båda modellerna: stabiliserad vilopose, bollträff och återgång med höftstöd, dragning via kamerans raycast och musfunktionerna, ett helt varv av varje klipp som motormål, balanshjälp av, passivt fall mot golvet samt återställning. Det kontrollerar också att den synliga benposen följer fysikkropparna, att reglagen följer med vid modellbyte och att gamla fysikkroppar tas bort. Händelserna är skriptade; det är inget automatiserat OS-musprov.

Det maskinläsbara resultatet finns i `docs/active-ragdoll-verification.json` och den fulla engine-rapporten i `output/zombie-beach/rodin-tpose-v1/godot-active-ragdoll-validation.json`. Viewportbilder av aktiv kropp, bollträff och slapp ragdoll finns i samma mapp. Provet godkänner kontakt, ändliga rörelser och posöverföring inom angivna toleranser; anatomiska ledgränser, deformation vid hårda fall och självbärande balans kräver fortsatt arbete. Ingen Rodin-tjänst används och steget kostar 0 Rodin-credits.

```sh
python3 tools/build_character_review.py
godot --headless --path output/zombie-beach/rodin-tpose-v1/godot-review --script res://physics_smoke.gd --fixed-fps 120 --log-file /tmp/active-ragdoll-test.log
godot --path output/zombie-beach/rodin-tpose-v1/godot-review --log-file /tmp/active-ragdoll-render.log -- --physics-snapshots
```

## GitHub Pages

The playable demo is published at [Nordic Forest · Fysiklabb](https://donnybystrom.github.io/nordic-forest/). In repository **Settings → Pages → Build and deployment**, select **GitHub Actions** as the source. The workflow **Character physics demo on Pages** builds and tests changes on `main`, then deploys the generated site. It can also be started with **Run workflow**. A failed browser test prevents deployment.

`tools/build_character_web.py` copies the tracked runtime catalog and its two hash-checked GLBs into `build/character-web/project/`, adds the authored reviewer, and exports to `build/character-web/site/`. Neither ignored generation jobs nor Blender is needed. The workflow pins Godot 4.7.1 and verifies its downloads with SHA-256. Build output stays outside Git; Pages receives an artifact containing HTML, JavaScript, WebAssembly and the resource pack. The first download is approximately 101 MiB before transfer compression.

The single-thread export uses Compatibility/WebGL 2 and built-in Jolt. It works on ordinary Pages hosting without cross-origin isolation headers. Start with **Starta fysiklabbet**; a desktop browser with mouse and keyboard is recommended. Q/E changes model, left/right changes clip, space pauses, R resets the body, B retrieves the ball, and 1/2/3 selects animation/active/passive mode. The on-screen controls expose the same choices.

To export locally, install Godot 4.7.1 and its export templates, then run:

```sh
python3 tools/build_character_web.py
python3 -m http.server 8010 --bind 127.0.0.1 --directory build/character-web/site
```

Open `http://localhost:8010/?mode=arena` for the FPS testground, or `http://localhost:8010/` for the character lab; loading the HTML directly from disk does not work. `tools/serve_character_web.command` starts this server on port 8010. To run the browser acceptance test, install Playwright 1.62.1 and its Chromium runtime, then run `node tools/test_character_web.cjs`. For an existing Chrome installation use `--channel chrome`. `--url https://donnybystrom.github.io/nordic-forest/` runs the same test against the hosted demo. Evidence is written under `build/character-web/verification/` and retained as a CI artifact.

The browser test uses actual canvas clicks, mouse dragging and keyboard events. It checks both characters, all 13 clip selections per character, ball contacts and displacement, spring dragging, passive falls, reset, pause and physics sliders. This verifies controls and the physics prototype; it does not establish anatomical accuracy, autonomous balance or performance on every device. The test reads diagnostics exposed only when `?test` is present. Normal use does not publish those diagnostic snapshots.

See [Godot web export](https://docs.godotengine.org/en/stable/tutorials/export/exporting_for_web.html) and [GitHub Pages publishing sources](https://docs.github.com/en/pages/getting-started-with-github-pages/configuring-a-publishing-source-for-your-github-pages-site).

## FPS-testground

Öppna [FPS-testbanan](https://donnybystrom.github.io/nordic-forest/?mode=arena), eller växla med länken i sidhuvudet. Det tidigare fysiklabbet finns kvar på samma webbplats. Lokalt startas banan med `tools/open_testground.command`; det bygger ett tillfälligt projekt från de granskade, spårade GLB-filerna och kräver inga genereringsjobb eller Blender.

| Kontroll | Funktion |
| --- | --- |
| Spela / klicka i banan | Fångar musen för FPS-vyn |
| WASD / Shift / Space | Gå, spring, hoppa; spelaren kolliderar med banan och zombierna |
| Mus / höger musknapp | Se dig omkring / sikta närmare |
| Vänster musknapp | Avfyra; håll in för automateld med profil 4 |
| R | Ladda om ett magasin med 12 skott; reservammunitionen är obegränsad |
| Tab / Esc | Visa inställningar / släpp musen |
| F2 | Visa de förenklade träff- och kollisionskropparna |
| 1 / 2 / 3 / 4 | Pistol, .44-spelprofil, hagelsvärm eller automateld; sätter även provimpulsen |

Menyn väljer 1–12 zombier, en eller båda modellerna, rörelse och spridd eller trängre formation. **Spawna om grupp** tillämpar de valen; **Lägg till en** använder samma modell-/rörelseval utan att byta ut de andra. Rörelserna är vilopose, ostadig gång, gång, löpning och krypning. Blandat ger olika klipp och tidsfaser. **Följ spelaren** ändrar beteendet direkt; avstängt begär ingen förflyttning medan animation och fysik fortsätter. Kroppen kan fortfarande knuffas bort från sin startplats.

Varje zombie har 17 fysiska kroppar och 16 leder, med kollisioner mellan olika zombier. Ragdoll-kropparnas föräldranod hålls stilla. Ledmotorerna följer animationens relativa rotation mellan barn och förälder och ger lika stora motriktade vridmoment på båda kropparna. De försöker därmed hålla en pose även under ett fall, utan att själva räta upp hela kroppen mot världen.

Testbanan använder en separat, begränsad balanshjälp. Den beräknar masscentrum och hastighet, stöd under fötterna och höftens lutning mot referensen. För krypning räknas även händer och ben. Faktiska golvkontakter kompletteras med markstrålar: en marginal på 20 cm och 0,16 s tillåter korta fotlyft i klippen. Förväntat masscentrum, inklusive 0,30 s av oönskad horisontell hastighet, jämförs med det breda stödområdet. Stödet minskar när kroppen hamnar utanför området eller lutar för mycket. Detta är en praktisk stabilitetsheuristik, utan stödpolygonlösare, fotplacering eller reaktionskrafter genom fotsulorna.

Det finns ingen horisontell fjäder mot startplatsen. Animationsreferensen följer den simulerade höften. Följandet begär i stället en hastighet och använder en begränsad drivkraft när balanshjälpen är tillgänglig. Upprättningshjälpen använder höjdkraft på höften och begränsade vridmoment på höft och bål. Den kan ge efter även vid krafter som kommer direkt från fysikmotorn. En enkel vägpunkt leder mot öppningen mellan väggarna. Det är ingen generell navigation, och fötterna kan fortfarande glida.

Pistolen är en procedurbyggd prototyp med synliga armar, siktning, vapengung, rekyl, mantelrörelse, mynningsljus, ljud, träffmarkör och tidsstyrd omladdning. Kameran bestämmer siktpunkten, sedan kontrolleras vägen till och från pipan så att närliggande skydd kan stoppa skottet även om pipan hamnar i eller bakom en vägg. Skottet stannar vid första intakta ytan; befintliga meshhål kan skjutas igenom när skaderefineringen används. Ingen ballistisk bana eller kvarvarande energi genom flera kroppar simuleras.

En kroppsträff ger `RigidBody3D.apply_impulse` en gång på den träffade benkroppen, med hävarmen i världskoordinater. Träffplats, riktning och kroppens massa påverkar förskjutning och rotation. Axelträffar från samma riktning kan därför vrida kroppen åt motsatta håll. Det används ingen förvald träff- eller fallanimation.

Profilerna **Pistol**, **.44**, **Hagelsvärm** och **Automateld** sätter totalimpulsen till 14, 70, 100 respektive 18 N s. Reglaget tillåter 2–180 N s. Hagelsvärmen använder åtta separata strålar med 2,2° spridning; varje stråle får en åttondel av budgeten. Missar överför ingen impuls, och hinder stoppar varje stråle separat. HUD visar levererad totalimpuls och antal kroppsträffar. 8 g vid 350 m/s har rörelsemängden 2,8 N s: dessa större provvärden är avsiktligt förstärkt spelrespons, inte kalibrerad ammunition. Samma prototyppistol används visuellt för alla impulsprofiler.

Skott släpper balanshjälpen en kort stund utifrån överförd rörelsemängd per kroppsmassa. Flera hagel i samma bildruta räknas ihop. **Själva impulsen eller fallet sänker inte muskelkraften.** Med meshskador aktiverade kan vävnadsförlust separat försvaga eller koppla bort muskler. Kroppen kan därför reagera och falla med aktiva leder. När höften faller under gränsen går agenten till `downed`, med upprättningshjälpen avstängd. Om **Res dig med animation och stöd** är på kan en lugnad kropp försöka resa sig efter minst två sekunder. Förloppet använder sekvenserna nedan och återgår sedan till sin tidigare rörelse. Vid en ny träff avbryts försöket; hastigheter och fysisk pose bevaras.

Bålens ledade kroppar kan vika sig; bukens mesh har ingen separat mjukvävnadssimulering. Anatomiska ledgränser, aktivt återhämtningssteg, kontaktstyrd fot-IK under gång, aktiv klättring och detaljerad mjukvävnadsfysik återstår. Den första versionen av muskelskador, meshhål och avskiljning beskrivs i [skadesystemets dokumentation](DAMAGE-SYSTEM.md).

### Uppresning från mage och rygg

Två lokalt skapade Godot-animationer finns i `get_up_prone.tres` och `get_up_supine.tres` under `integrations/godot/testground/`. De är små resurser med nycklade kanaler för höft, bål, rullning, händer och fötter. `recovery_motion.gd` samplar kanalerna med mjuk interpolation och löser armar och ben som kedjor med två länkar efter varje riggs egna benlängder. De ursprungliga GLB-filerna och deras 13 klipp behålls.

- **Mage:** handstöd → pressa upp bålen → dra in knäna → sätt fram en fot → res dig.
- **Rygg:** rulla åt sidan → sitt upp → vänd upp på knä → res dig.

Bröstets faktiska riktning avgör sekvens. Riktningen mot huvudet längs golvet ger manöverns orientering på kroppens nuvarande plats. En ingångsblandning på 0,65 s går från de simulerade kropparnas rotationer till första posen; efter sekvensens 4,6 respektive 4,9 s blandas målen tillbaka till en fast ingångspose i den ursprungliga rörelsen över 0,8 s. Rörelsens tidslinje pausas under uppresningen och startar från ingångsposen när blandningen är klar. Normal förföljning återupptas först när kroppen är uppe och tillräckligt upprätt.

Animationen styr motorernas mål; under uppresningen tillkommer begränsad hjälp med kroppsorientering, höjd och hand-/fotplacering. Hjälpen tonas in och ut, och kollisioner är fortsatt aktiva. Det är en assisterad uppresning, inte en självförsörjande biomekanisk lösare. Placeringshjälpen gäller bara denna manöver, på ett plant referensgolv; gångens fotarbete och kontaktanpassning på ojämn terräng återstår. En blockerad sekvens ger upp efter en tidsgräns och kan senare försöka igen. Inga kroppstransformer skrivs och inga hastigheter nollställs under verkliga fall, uppresningar eller avbrott.

För ett reproducerbart prov: välj **Uppresningsprov · mage** eller **Uppresningsprov · rygg** i rörelsemenyn och klicka **Spawna om grupp**. Denna särskilda start placerar nya kroppar liggande en gång vid spawn; därefter sker allt med simulationen. Slutposen övergår till ostadig gång. Stäng av **Res dig med animation och stöd** för att låta dem ligga kvar. HUD visar aktuell uppresningsfas.

`recovery_smoke.gd` provar båda sekvenserna på båda modellerna: riktningsval, alla faser, övergångarnas kontinuitet, bibehållen muskelkraft, återupptagen förföljning, skottavbrott, nytt försök och otillräcklig takhöjd. Webbläsarprovet väljer båda liggande starterna via den riktiga menyn och inväntar avslut på båda modellerna. Resultaten sparas i `build/character-web/recovery-validation.json` och CI:s verifieringsartefakt.

`integrations/godot/testground/` innehåller arena, FPS-spelare, zombieagent och fysikprov. Den delade ragdoll-kontrollern används även av det tidigare labbet. `smoke.gd` provar olika modeller och rörelser, stillastående mål, fysisk förföljning, träff i huvud/underarm med vridning, skymmande vägg, skottspärr/omladdning, nedslag/assisterad återhämtning och kollisioner mellan gruppmedlemmar. `tools/test_testground_web.cjs` använder riktiga webbläsarhändelser för gruppval, musfångst, WASD, siktning, skott, omladdning och följande. Det separata `impact_smoke.gd` jämför svag/stark bålträff, båda axlarnas motsatta vridning, direkt yttre impuls, kvarvarande muskelkraft, slutlig förskjutning, rotation utan markstöd och hagelbudget på båda modellerna. Webbläsarprovet skjuter också med tung profil och hagel genom riktiga mus-/tangentbordshändelser. Proven körs före Pages-publicering. De godkänner funktion och begränsad fysikstabilitet, inte anatomisk realism eller en generell FPS-prestandanivå.

```sh
python3 tools/build_character_web.py
godot --headless --path build/character-web/project --fixed-fps 120 --script res://testground/smoke.gd --log-file /tmp/testground-physics.log
godot --headless --path build/character-web/project --fixed-fps 120 --script res://testground/impact_smoke.gd --log-file /tmp/testground-impacts.log
godot --headless --path build/character-web/project --fixed-fps 120 --script res://testground/recovery_smoke.gd --log-file /tmp/testground-recovery.log
node tools/test_testground_web.cjs --channel chrome
```

Resultatet från motorn sparas i `build/character-web/testground-validation.json`, webbläsarens rapport och bilder i `build/character-web/verification/testground/`. CI bevarar dem i verifieringsartefakten. `--url https://donnybystrom.github.io/nordic-forest/` testar den publicerade FPS-banan. `?test` aktiverar enbart läsbara diagnostiksnapshots i webbläsaren; vanliga spelare får inte den löpande diagnostiken.

## Rörelseöverföring

`tools/retarget_character_motions.py` körs i isolerad Blender och bakar kvinnans rörelser till mannens rigg. De delar 22 kroppsben. Kvinnans T-pose och mannens A-pose förenas genom riktningsanpassade referensramar, därefter överförs rotationerna i modellrymden tillbaka till målriggens lokala benrymder. Målets egna benlängder behålls; höftens förflyttning skalas med höjdrelationen 0,94. Klippens ursprungliga namn och tider behålls, med 30 bakade prover per sekund.

Källorna är `assets/models/zombies/rodin-tpose-working-v1/Rodin_TPose_Working_v1.glb` och mannens `assets/generated/characters/beach-tourist-zombie-v1/rig-cb6fe14f57ac0f5e/character-rigged.glb`. Den nya leveransen ligger i `assets/generated/characters/beach-tourist-zombie-v1/shared-motions-v1/`: `character-animated.glb`, redigerbar `.blend` och `retarget-report.json`.

```sh
/Applications/Blender.app/Contents/MacOS/Blender --background --factory-startup --disable-autoexec --python-exit-code 1 --python tools/retarget_character_motions.py -- \
  --source assets/models/zombies/rodin-tpose-working-v1/Rodin_TPose_Working_v1.glb \
  --target assets/generated/characters/beach-tourist-zombie-v1/rig-cb6fe14f57ac0f5e/character-rigged.glb \
  --output assets/generated/characters/beach-tourist-zombie-v1/shared-motions-v2
```

Använd en ny versionsmapp; verktyget skriver inte över tidigare leveranser. Ingen Rodin- eller annan betald tjänst anropas i detta steg: **0 ytterligare Rodin-credits**.

Mannens rigg saknar kvinnans 30 fingerben. Händerna följer kroppsklippen men fingrarna har ingen separat animation. Fotkontakt, fingerställningar, ledvolym och självskärningar behöver fortsatt granskning. Ursprungliga kontaktfel följer med, och olika kroppsproportioner kan skapa fler; godkända transform- och exportprov innebär inte godkänd gameplay-deformation.

## Fler karaktärer

`config/character-review-catalog.json` är katalogen; gränssnittet räknar inte med exakt två modeller. Lägg till en post med unikt ID, visningsnamn, käll-GLB, scenadress, benantal, texturstorlek, viktformat och viloposnamn. GLB:n ska innehålla en `AnimationPlayer`, ett `Skeleton3D` och de klipp som ska visas. Baka först om klippen till dess egen rigg vid behov.

Varje GLB ska ha en **egen mapp** i Godot-projektet. Importören kan annars skriva över en annan modells extraherade texturer med identiska namn. Kvinnans 2K- och mannens 4K-texturer ligger nu åtskilda. Kör `python3 tools/build_character_review.py` eller startfilen för att kopiera uppdaterade tillgångar, katalog och skript. Implementationen finns i `integrations/godot/character-review/`.

Fysikprototypen kräver de 17 Mixamo-namngivna kroppsbenen och slutpunkterna i `ActiveRagdoll.SEGMENTS`, meter som längdenhet och en rigg utan extra världsskalning. Andra kroppsformer behöver egna granskade kollisionsformer, massor och ledgränser. Katalogens valfria `physics_mass_kg` styr den simulerade totalmassan; standardvärdet är 80 kg.

Godots animationsoptimering och komprimering är avstängda i granskningsimporterna för att behålla referensnycklarna. Kameran följer höften. Animationsläget behåller root motion; fysikläget använder horisontell rörelse på plats. Loopning aktiveras i granskningsinstansen.

## Animationsverifiering från 2026-10-22

| Prov | Resultat |
| --- | --- |
| Blender-bakning | 13 klipp, 1 607 bildrutor; 65 jämförelseposer, största rotationsavvikelse cirka 0,000018° |
| GLB återimport i Blender | 65 deformerade meshprover, största vertexavvikelse cirka 0,0185 mm |
| Godot 4.7.1 import och uppspelning | 52 respektive 22 ben och skin binds; 13 klipp vardera; 130 ändliga rörelseprover; 988 lösta spårsökvägar; största tidsavvikelse 0,00000045 s |
| Material | Kvinnan behåller 2K och åtta vikter; mannen behåller 4K och fyra vikter |
| Kontroller | 26 klippval; paus, sökning och återstart; viloposåterställning; bevarad fas/hastighet/paus vid modellbyte; knapparnas omslag och tangenthanterare |
| Utbyggbarhet | En tredje katalogpost med samma testtillgång kan väljas; exakt en aktiv karaktär efter byten |
| Faktisk rendering | Fyra viewportbilder: gång och krypning på båda, Apple M1 Pro, OpenGL Compatibility; visuellt granskade |

Maskinläsbara resultat finns i `docs/character-review-verification.json`. Fulla engine-rapporter och bilder ligger i `output/zombie-beach/rodin-tpose-v1/`. Tangenthanterare och UI-signaler har provats; fysiska musgester har inte automatiserats. Ingen prestandamätning, fotkontakt- eller fysikacceptans görs av dessa prov.

```sh
python3 tools/build_character_review.py
godot --headless --path output/zombie-beach/rodin-tpose-v1/godot-review --editor --import --log-file /tmp/character-import.log
godot --headless --path output/zombie-beach/rodin-tpose-v1/godot-review --script res://smoke.gd --log-file /tmp/character-assets.log
godot --headless --path output/zombie-beach/rodin-tpose-v1/godot-review --script res://ui_smoke.gd --log-file /tmp/character-ui.log
godot --path output/zombie-beach/rodin-tpose-v1/godot-review --log-file /tmp/character-render.log -- --snapshot-all
```

Kontrollera både PASS-markörerna, JSON-rapporterna och eventuella skriptfel; processens exitkod ensam räcker inte vid ett parsingsfel i Godot.
