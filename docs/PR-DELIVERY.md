# Lokal PR-orkestrering

Beslut 2026-10-18: rollerna behöver **inte** separata GitHub-identiteter. En lokal orkestrator använder användarens GitHub-anslutning. GitHub lagrar kod, diffar, kommentarer, PR:er och CI-resultat; lokala jobb håller reda på roll, indata, konfiguration, granskning och beslut. En ny GitHub App är inget krav för denna modell.

## Installerad första version

**NF · PR Control** finns under Langflows Saved-komponenter och som flödet **04 — PR Control**. Lägg komponenten i ett flöde, slå på Tool Mode och koppla Toolset till den orkestrerande Langflow-agentens Tools när dynamiska PR-anrop behövs. Endast JSON-kommandot är ett verktygsargument. Execute live väljs av flödesförfattaren; det möjliggör GitHub-anrop och, vid review_pr, ett debiterat modellanrop. Förhandsgranskning gör inga externa anrop.

```json
{"action":"inspect","number":6}
```

| Kommando | Funktion |
| --- | --- |
| `inspect` | Hämtar aktuell PR, diffens filinventering, kommentarer, reviews och olösta trådar. Ny inspektion läser färsk GitHub-status. |
| `create` | Skapar en draft-PR från `branch`, `title`, `body`; återanvänder en befintlig öppen PR. Grenen ska redan vara pushad under agent/ eller codex/. |
| `overview` | Publicerar/uppdaterar en markerad översiktskommentar med ansvariga enheter, granskarroller och granskningsunderlag. |
| `review_pr` | Kör en lokal kodgranskningsprofil: ange `number` och `role`, exempelvis qa eller curator. Resultatet binds till PR, head, base, diffhash, roll, profilhash och API-session. |
| `publish_review` | Publicerar ett färdigt lokalt granskningsjobb (`review_job`) som en riktig GitHub-review med event COMMENT. Giltiga fynd på tillagda rader läggs som inline-kommentarer. |
| `merge_small` | Prövar policyn och gör squash-merge endast om alla villkor uppfylls; ange `review_jobs` med två aktuella granskningsjobb. |

Samma skrivkommando och Submission key återanvänder sitt jobb. Ändra nyckeln för en avsiktlig ny körning, till exempel när en översikt ska uppdateras för en ny commit. Efter ett oklart GitHub-skrivresultat stoppas jobbet för avstämning; det återspelas inte automatiskt. API-nycklar och GitHub-token ligger inte i flödet eller verktygsargumenten. Repot styrs av lokal policy; det finns inget argument för valfritt repo, generell shell eller administrativa bypass-flaggor.

Även CLI finns:

```sh
/opt/miniconda3/bin/python3 -m forest_agents.pr_delivery inspect 6
/opt/miniconda3/bin/python3 -m forest_agents.pr_delivery overview 6 --apply
/opt/miniconda3/bin/python3 -m forest_agents.pr_delivery create --branch codex/min-feature --title 'Avgränsad ändring' --body-file docs/pr-body.txt --apply
/opt/miniconda3/bin/python3 -m forest_agents.pr_delivery review 6 --job-id JOB_ID --apply
/opt/miniconda3/bin/python3 -m forest_agents.pr_delivery merge-small 6 --review-job CURATOR_JOB --review-job QA_JOB
```

CLI:s merge-small är en kontroll utan merge tills --apply anges. Langflow-kommandot merge_small med Execute live aktivt begär både kontroll och merge. Kodarbetaren/Codex hanterar lokala ändringar, commit och push på sin avgränsade gren; PR-bryggan exekverar inte godtyckliga Git-kommandon från en modell.

## Mandat som kan växa

`config/pr-policy.json` routar ändrade filer till ansvariga enheter. Första automatiska merge-kategorin omfattar högst sex vanliga dokumentationsfiler under docs/, högst 200 ändrade rader, inga filraderingar eller namnbyten. Produktkrav, roadmap, beslut, agentinstruktioner, policy, exekveringsbehörigheter, CI och okända områden är undantagna. Övriga kod-/assetändringar går till ansvarig enhet; den första automatiska kategorin täcker dem ännu inte.

En liten dokumentations-PR behöver aktuella lokala godkännanden från **Knowledge Curator och QA**, gröna kontroller inklusive contracts från Agent harness checks, en öppen PR som är redo, inga olösta inline-trådar eller kvarstående REQUEST_CHANGES. Ingen människa behöver godkänna varje sådan PR. Två kommentarer från samma roll räcker inte. Äldre commit, ändrad base, annan diff eller ändrad granskningsprofil gör underlaget inaktuellt. Head/base och kontroller läses om före merge; serveranropet binder exakt head-SHA och använder inget admin-undantag.

De sparade 15 agentdefinitionerna behåller sina planeringsinstruktioner. review_pr väljer en uttrycklig **sessionsspecifik kodgranskningsprofil** och LocalPRReview-schema, med sparad rollidentitet/modell men utan verktyg, implementation eller delegation. Den effektiva profilhashen sparas. Vanliga Handover-resultat med COMPLETE kan inte godkänna kod. För stor/ofullständig diff ger review_needs_scope och inget godkännande. Det nuvarande grundpaketet i PR #6 ligger utanför den lilla automatiska kategorin.

Lokala rollbeslut publiceras under det gemensamma GitHub-kontot, med roll, jobb/session och commit angivna. De använder COMMENT i GitHub och räknas av den lokala policyn, inte genom att låtsas vara separata användare eller mänskliga GitHub-approvals. Om man senare väljer GitHub-regler som kräver en annan användares native approval gäller de reglerna även för bryggan; dagens modell förutsätter inte sådana identiteter. Policyn skyddar anrop genom vår brygga, inte varje möjlig GitHub-klient på datorn.

## Fynd, korrigering och återställning

PR:ens Conversation visar översikt/beslut, Files changed visar inline-fynd och Checks visar körda kontroller. Ett fynd ska innehålla problem, fil/rad där möjligt, begärd ändring och hur fixen ska verifieras. Kodarbetaren svarar i tråden med fix-commit och faktisk testning. Granskaren kontrollerar den nya revisionen innan tråden markeras löst. V1 kan läsa trådar och publicera reviews; den startar ännu inte en obevakad fix-loop eller löser trådar själv.

Varje Git-commit är ett återställbart kodläge. Jobbens SQLite-checkpointar bevarar uppdrag, konfiguration, sessioner och resultat och kan återuppta identifierad körning. Efter merge görs återställning som en **ny revert-commit och PR**, så att historik och granskningsspår finns kvar. Ett Git-revert återställer kodfiler; redan skickade API-anrop, publicerade kommentarer eller andra externa effekter behöver avstämning/kompensation. Checkpoint är inte en komplett snapshot av en pågående operativsystemsprocess.

## Verifiering

57 enhetstester kontrollerar bland annat lokala rollgodkännanden med ett gemensamt GitHub-konto, inaktuella head/base/diff/profiler, blockerande fynd, väntande/felaktiga kontroller, olösta trådar, känsliga ändringar och PR-idempotens. Verklig inventering av PR #6 och återanvändning av dess befintliga PR har testats. Två verkliga agentkörningar testade kodgranskningsprofilen på en **syntetisk dokumentationsfixture**; de är inga godkännanden av PR #6. Integrationsevidens finns i docs/pr-delivery-verification.json.
