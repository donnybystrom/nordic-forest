# Beachside Revenant: meshreparation v1

Verifierad 2026-10-21 i Blender 5.2.0 LTS via den aktiva MCP-bryggan. Detta är en reparerad experimentmodell och mätunderlag för rörelse; ingen aktiv ragdoll, Godot-acceptans eller frakturering ingår.

## Levererade modeller

- [Riggad GLB med alla 11 klipp](../../../assets/models/zombies/repaired-v1/Beachside_Revenant_Repaired_v1-Mixamo.glb)
- [Ren, redigerbar Blender-källa](../../../assets/models/zombies/repaired-v1/Beachside_Revenant_Repaired_v1.blend)
- [Granskningsscen med original, reparation och röd kontaktmarkering](Beachside_Revenant_Repair_Review_v1.blend)
- [Före/efter: löpning](running-before-after.png), original till vänster och reparation till höger.
- [Tre matchade animationsposer](before-after-comparison.png), original till vänster och reparation till höger. Pose-/kameraunderlag finns i `comparison-poses.json`.

Din ursprungliga öppna scen sparades före arbetet som `live-scene-checkpoint.blend`. Originalscenen finns också kvar i den öppna Blender-sessionen. Källfilerna har inte skrivits över.

## Vad mätningen hittade

Alla tre levererade exportmallar har bitidentiska positions-, normal-, UV- och triangelindex-arrayer. De har vardera 66 ben och 11 klipp. Byte mellan exportmallarna löser därför inte den här geometriskadan. [Inventering](source-inventory.json), [källintegritet](source-integrity.json).

Direkta meshkanter förenade fingerviktade ytor med lårviktade ytor: 478 vänsterarm–vänsterben-kanter och 366 högerarm–högerben-kanter enligt dominerande viktregion. Små kanter blev långa membran när handen flyttades bort från låret. Även svaga felvikter utanför sömmen gav synliga fel; några underarmsvertices påverkades av bäckenet.

## Reparation

- 803 ursprungliga bryggtrianglar togs bort, liksom 22 små öppna kontaktrester.
- 8 007 källvertices fick korrigerade icke-lokala vikter före efterföljande lokal viktutjämning.
- Exakt sammanfallande exportseams svetsades endast inom samma anatomiska region; UV-data behålls per face corner.
- 11 klämda gränsvertices separerades. 16 kontaktöppningar slöts med 691 nya trianglar.
- Kvarvarande fingerliknande lårutskott jämnades ut lokalt; 1 287 vertices flyttades. Största förflyttning är cirka 6,3 cm, så detta omfattar faktiskt omformad kontaktgeometri.
- Viktövergångar vid axlar/armhålor jämnades ut på 2 232 vertices. Felaktig underarmspåverkan bortom handleden korrigerades på ytterligare 377 vertices. Dessa mängder kan överlappa.
- Exporten använder högst åtta benvikter per vertex. Fyra nya patch-centervertices behövde begränsas till åtta influenser. Att kapa hela meshen till fyra vikter försämrade de mjuka övergångarna och används inte i slutfilen.

Den redigerbara meshen har 48 114 vertices och 96 320 trianglar. GLB-återimport ger 58 553 vertices eftersom UV- och materialgränser delar vertices vid export; dessa tal innebär inte en jämförbar prestandaförbättring.

`repair-changes.json` innehåller ursprungliga vertex-/face-ID:n, regioner, patchar och ändringsmängder. Mesh-attributen `source_vertex_id`, `source_face_id` och `anatomical_region` finns i Blender-källan. Nya patchar har `source_face_id=-1`; nya patch-centervertices har `source_vertex_id=-1`.

I granskningsscenen är `ZB_Source_Mesh` originalet och `ZB_Repaired_Mesh` reparationen. `ZB_Audit_ContactFaces_803` markerar de borttagna bryggtrianglarna i rött. Visa en av dessa meshkopior åt gången; de ligger på samma plats och använder samma källrigg. Den öppna sessionen visar reparationen med `Unsteady_Walk` aktiv.

## Verifiering

| Kontroll | Resultat |
| --- | --- |
| Matchade animationsprover | 1 132 poser per mesh, fördelade över alla 11 klipp; varje helt Blender-frame och varje klipps slutpunkt vid källscenens 24 fps |
| Största uppmätta kantförlängning | Original: 1,2637 m. Reparerad: 0,0454 m |
| Kanter som växer mer än 5 cm i proverna | Original: upp till 2 007 samtidigt. Reparerad: 0 |
| Slutmeshens topologi | 0 öppna kanter, 0 icke-manifold kanter, 0 lösa vertices; Blender mesh validation gör inga korrigeringar |
| GLB-innehåll | 1 scen, 1 mesh med 5 materialprimitiver, 1 skin, 66 ben och 11 klipp |
| Klipptider | Bevarade med 30 fps-export och avrundning av numeriskt nästan heltaliga keyframe-tider |
| Återimportens poseprov | 55 poser över alla 11 klipp; största vertexavvikelse cirka 0,070 mm mot exportkällan |
| Originalfiler | SHA-256 oförändrad för samtliga tre GLB-filer |

Topologin skiljer sig före/efter. Kantmåtten är maxima över respektive mesh vid matchade tider, inte en jämförelse av en oförändrad kantlista. Proverna bevisar inte alla kontinuerliga tidpunkter eller frånvaro av självintersektioner.

Fulla rapporter: [jämförelsemått](comparison-metrics.json), [återimportkontroll](roundtrip-validation.json), [leveransmanifest](deliverable-manifest.json), `source-full-deformation-audit.json` och `repaired-full-deformation-audit.json`.

## Underlag för procedurrörelse

[motion-targets.json](motion-targets.json) innehåller 1 402 uppmätta poser vid 30 Hz från samtliga 11 klipp: lokala rotationsmål för 22 kroppsrörelseben samt huvud-, hand-, fot- och tåankare relativt bäckenet. [motion-summary.json](motion-summary.json) sammanfattar klipptider, skillnaden mellan start-/slutpose och höjdbaserade kontaktkandidater.

Koordinaterna är Blender Z-up i meter; quaternions lagras som w,x,y,z. En framtida Godot-adapter måste konvertera koordinaterna. Kontaktkandidaterna är endast höjdtrösklar och bevisar inte planterade fötter, rätt stödkraft eller en gångcykel. UUID-klippen har behållit sina namn.

Nästa steg kan använda dessa mål i en fasstyrd rörelsegenerator, markanpassad IK och därefter en fysisk kropp som försöker följa målen. Att tappa en lem ska ändra tillåtna kontakter och rörelsemål. Datat innehåller ingen sådan kontroller ännu.

## Begränsningar

De grova hand–lår-membranen är åtgärdade. Ursprunglig hand-/fingeranatomi, axlar, hår och kläddetaljer behöver fortfarande konstnärlig granskning, särskilt i extrema poser. Slutna triangelytor betyder inte anatomiskt korrekt topologi eller att varje rörelse saknar kollisioner genom kroppen.

De återskapade kontaktytorna använder fyra enkla hudmaterial, med färger provtagna från närliggande textur. Förlorad insidesgeometri och texturdetalj kan inte återvinnas ur den sammansmälta källan med säkerhet; patcharna är en reparationsapproximation. Originalmaterialet och dess texturer används på övriga ytor.

Ingen spelmotor, aktiv ragdoll, skadefunktion eller Godot-prestanda har verifierats. GLB-filen är exporterad och kontrollerad i Blender, inte accepterad som färdig spelkaraktär.

## Verktygsspår

De avgränsade skripten finns i `tools/zombie_beach/`. Körordningen är `prepare_scene`, `measure_deformation` för källan, `repair_contact_bridges`, `close_contact_surfaces`, `smooth_rebuilt_thighs`, en ny `measure_deformation` med prefix `repaired`, `smooth_shoulder_weights`, `clean_wrist_weights`, `limit_skin_influences`, täta slutmätningar, `export_repair` och `validate_roundtrip`. `extract_motion_targets` och `render_comparison` producerar rörelse-/bildbevis. De är projektspecifika Blender-steg med explicita scen- och objektnamn; detta är ännu ingen installerad Langflow-operation.
