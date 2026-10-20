# GitHub planning and explicit agent work

Open the private [Nordic Forest board](https://github.com/users/donnybystrom/projects/2). GitHub Issues are the editable work records; Projects supplies the views. GitHub keeps one shared account. **Owner Role** names a local saved agent, not another GitHub identity.

- **Board:** work by Status.
- **Feature Map:** native parent/sub-issues, delivery milestone and progress.
- **Sprint Plan:** existing planning tags; these are text labels, not dated iteration commitments.
- **Ready for agents:** bounded planning work whose visible contract is ready to dispatch.
- **Needs input:** blocked work, with the missing evidence or unblocking action in **Blocker**.

A0 covers the agent workflow foundation; R0 covers the reference asset slice; M0 covers the renderer/authoring decision. Milestones have no committed dates. Features, stories and tasks/spikes use native issue hierarchy. Existing cards remain open pending their acceptance review, including after PR #6 merged.

## Running a ticket in Langflow

Use **05 — Planning Board** in Nordic Forest, or **Components → Saved → NF · Planning Board** in another flow. The component exposes one Tool Mode string argument, `request_json`. The flow author controls **Execute live** and the submission key. Live is off by default. No new MCP server is needed.

1. Run `{"action":"inspect"}` with Execute live enabled for current GitHub state.
2. Choose a Ready ticket, for example `{"action":"dispatch_plan","issue":7}`. This explicitly launches one billed saved-role planning session through the local single-worker bridge.
3. The issue moves to **In Progress** with an **Agent Job** ID. The typed handover is posted as an issue comment, and the card moves to **In Review**, or **Blocked** if the agent needs input. Inspect the local dashboard if it remains queued or running.

There is no unattended polling, automatic implementation loop, or automatic parent-feature acceptance. A planning session has no shell or GitHub tool access; the broker performs the typed board operation. The existing [PR Control](PR-DELIVERY.md) handles code-review and delivery separately.

## Editable work contract

Each runnable ticket has a visible JSON block in its issue body, between `nf-ticket-spec` markers. Edit it in GitHub. It names a portable `NF-T…` identity, role, objective, acceptance items, allowed paths, non-goals, prerequisite issue numbers and unresolved questions. Paths describe future work scope; they do not grant file-writing tools to the planning session. Prerequisites must be closed and questions resolved before Ready/dispatch. **Owner Role** must agree with the contract. GitHub comments and linked reference files are not automatically pulled into agent context; the validated contract and configured role context files are supplied explicitly.

The broker rejects duplicate IDs, unsafe scope paths, unexpected roles and credential-like input. Ticket creation reuses an identical contract and preserves existing manual field values. Parent assignment refuses to replace an existing different parent. To revise a contract, edit the existing GitHub issue rather than calling creation with a changed spec.

Example state update after inspecting the current card:

```json
{"action":"set_state","issue":8,"expected_state":"Todo","state":"Ready"}
```

Other commands: `create_ticket` accepts `ticket`, optional `parent_issue` and native `milestone` number; `sync_job` accepts `job_id`; `link_pr` accepts `issue` and `pr`. Linking adds `Refs #…` to an open repository PR and stores its URL as evidence. Only explicit `close_on_merge: true` for a concrete Task adds `Closes #…`. A reference alone is not a closing relationship or guaranteed Linked pull requests field entry. The broker does not close issues; **Done** requires the issue to be already closed.

## Recovery and concurrency

The local SQLite job record is durable. A dispatch key binds the issue number and canonical contract hash; repeating dispatch reuses that child job, even after completion. A changed contract cannot start while an earlier ticket job is active or unreconciled. There is one bridge worker; do not run a second bridge against the same database. Identical-contract reruns need explicit reconciliation rather than a new submission key.

GitHub and SQLite do not share a transaction. A child job is saved before publishing board metadata, and a `board_dispatch_created` event retains its issue number. If publication fails, inspect the retained job and GitHub card, restore the exact **Agent Job** ID and **In Progress** state only if appropriate, then call `sync_job`. Do not create a replacement run. Ambiguous remote writes are interrupted for reconciliation, not retried automatically.

Automatic handover sync checks both the bound job ID/current state and the unchanged contract. It preserves later human changes. These checks are optimistic: simultaneous external edits during the final API writes can still race. Sync failures retain the completed local artifact and emit `board_sync_failed`; retry `sync_job` after reconciling. Comment publication is idempotent by job marker; inventories deliberately fail closed above their current page limits (100 comments / 1000 issues or board items).

No game scene, mesh conversion, rendered comparison or hardware performance is certified by this workflow. [Verification](planning-board-verification.json) records the actual integration checks.
