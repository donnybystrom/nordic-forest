# Indie workflow: GitHub Projects, reviewed changes and portable work items

Decision on 18 October 2026: use **GitHub Projects**, not Azure DevOps. Repository: `donnybystrom/nordic-forest`. The local job runtime remains usable without a connected board, so a new experimental project does not need a corporate workspace.

Use Projects for editable scope, priority, sprint and feature/story organization. Use repository issues and sub-issues for the work, and pull requests for code review. The local runtime stores execution state and evidence. The portable source plan is `data/github-project-plan.json`; remote IDs belong in `config/github-project.json`. Bootstrap preserves human-edited fields on existing items rather than repeatedly resetting the board to the original plan.

## Structure adapted from SAFe and Conway

A small cross-functional group owns a feature from request to measured acceptance. Product Lead owns intent and priority; Technical Lead owns technical boundaries; the relevant implementation/art/reference/rendering specialists work together; QA supplies independent evidence review. Tooling enables those groups. Avoid turning each specialist prompt into a separate team that throws work over a wall.

Keep scope, source revisions, deliverables, actual checks, remaining uncertainty and next owner in every handover. Quality requirements run through each feature: contract checks during planning, source identity during acquisition, import and visual checks during conversion, and frame-time evidence in the actual renderer. Use an integrated demo for significant features. No release train or additional hierarchy is required for the current project size. This is an adaptation of selected practices, not a claim of complete SAFe adoption. [SAFe Team and Technical Agility](https://framework.scaledagile.com/team-and-technical-agility-discipline), [Conway discussion](https://martinfowler.com/bliki/ConwaysLaw.html).

## Board setup

Initial items: the durable visual agent workflow feature; its planning and agent-review stories; R0-001 asset conversion; M0 playable benchmark. Kind, Priority, Sprint, Feature and Evidence are separate fields. The initial bootstrap uses a portable Sprint text field; GitHub's native Iteration field supplies dated iterations when configuring the board's sprint schedule. Do not treat “Pilot 1” as a committed calendar deadline.

Recommended views: Board by Status; sprint table grouped by Sprint/Iteration; feature view grouped by Feature; roadmap after assigning target dates. A board adapter need not determine the project's sprint dates or promise delivery on the user's behalf. [Iteration fields](https://docs.github.com/en/issues/planning-and-tracking-with-projects/understanding-fields/about-iteration-fields).

```sh
/opt/miniconda3/bin/python3 -m forest_agents.github_board
/opt/miniconda3/bin/python3 -m forest_agents.github_board --apply --owner donnybystrom --repo donnybystrom/nordic-forest
```

Preview is offline. Apply explicitly uses the existing GitHub CLI credential, creates/reuses the named board and marked repository issues, then records mappings. In this desktop session, CLI use inside the sandbox could not access the working Keychain credential; repo reads worked outside it. Projects additionally required the user to grant the `project` OAuth scope. No tokens belong in project files or flow JSON.

## PR and CI strategy

One bounded feature branch → draft PR → independent agent review evidence and actual CI → human review when the feature mandate requires it → merge after the configured checks. Keep test evidence tied to the reviewed commit; new changes require new checks. The supplied CI runs offline Python contracts and a repository-input guard. Blender/visual/GPU acceptance is a separate job with appropriate hardware, not a successful Linux unit-test claim.

The local orchestrator uses one shared GitHub account. Roles, reviewer decisions and execution provenance are local identities tied to exact Git revisions, not separate GitHub users. Separate bots/apps are optional if native GitHub approval requirements are wanted later; they are not a prerequisite for local role-based orchestration. The PR broker can publish role-labelled COMMENT reviews and merge small documentation changes after two validated local code-review jobs and CI. It never treats a planning Handover as code approval or fabricates a human approval. See [the implemented PR routine](PR-DELIVERY.md).

GitHub's free plan includes Issues and Projects. Required-review/branch-protection availability differs for private repositories; do not claim it is enforced just because a workflow YAML or review template exists. [GitHub plans](https://github.com/pricing), [protected branches](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-protected-branches).

## Why this choice

GitHub Projects minimizes setup when issues, PRs and CI already live on GitHub. Linear is a good dedicated planning UI, but its current free plan has two teams and 250 issues. Plane Community Edition offers a self-hosted alternative with cycles/modules and an API; hosting and maintaining it is an additional responsibility. These remain possible adapters, not mandatory dependencies. [Linear pricing](https://linear.app/pricing), [Plane Community Edition](https://plane.so/open-source).

Keep portable IDs, parent links, sprint assignment, state, acceptance criteria, evidence and external provider mappings separate. Migration can then transfer those records instead of rewriting agent prompts around one vendor's UI. The current adapter bootstraps a board; continuous bidirectional synchronization and conflict resolution are not implemented.
