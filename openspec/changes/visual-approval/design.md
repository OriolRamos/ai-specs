## Context
Approval today (standard section 8) means two things:
- `ai-specs approve` posts `<!-- ai-specs:approval digest=… commit=… by=<login> -->` from the approver's terminal;
- `check-approval` counts such comments when their author is the `by` login and their digest is current.

The owner wants to approve from the GitHub UI, including on a phone, and to see in plain language what the digest
stands for. This design adds a second way to produce the same kind of record, with the same digest and the same
gate, and states what it can and cannot prove.

## 1. The card

### Where and when
One comment per issue, authored by `github-actions[bot]`. Its first line is the hidden marker:
```
<!-- ai-specs:approval-card change=<id> issue=<n> digest=sha256:<64 hex> commit=<40 hex> -->
```
The sticky card is the **oldest** comment on the issue by `github-actions[bot]` whose body starts with
`<!-- ai-specs:approval-card`. Newer duplicates (from a race) are left alone. A tick on a duplicate is undone, and
the duplicate says "use the first card".

The card is (re)rendered on:
- `issues: opened | edited | reopened`, when the issue has the `type:change` label;
- `push` to `change/**`.

It is not rendered when any of these holds:
- the issue is closed;
- the managed block is missing;
- the block's `branch:` does not match `^change/<n>-[a-z0-9][a-z0-9-]*$`, where `<n>` is this issue's number;
- the change id does not match `CHANGE_ID_RE`;
- the branch or the change folder does not exist yet.

In those cases the run ends with a notice in its log and writes nothing, so an issue opened before its branch gets
its card on the first push.

For a `push`, the issue number comes from the branch name (`change/<n>-…`). A branch whose issue's block names a
different branch is ignored, so a stray branch cannot rewrite another issue's card.

### Content (rendered by `scripts/card.py`, pure function of the folder at the commit plus issue metadata)
```markdown
<!-- ai-specs:approval-card change=visual-approval issue=8 digest=sha256:… commit=… -->
### Approval card · `visual-approval` · size L
Branch `change/8-visual-approval` at [`1a2b3c4d5e6f`](…/commit/<sha>) · digest `1a2b3c4d`

**Why**
<text of ## Why, up to 600 characters, cut at a line end, then "… [read the full proposal](…)">

**What changes**
<text of ## What Changes, up to 1500 characters, same rule>

**Not to add**
<text of ## Not to add, up to 800 characters, same rule>

**Requirements (9)** ASP-111 — … · ASP-112 — … (one line each, ids and titles from every delta spec)
**Tasks** 18, of which **3 human gate**: 6.1 …, 6.3 …, 6.4 … (task numbers and their first 80 characters)
**Sensitive paths named:** `.github/workflows/`, `openspec/roles.yaml` (or "none")

Read before approving: [proposal](…/blob/<sha>/openspec/changes/<id>/proposal.md) · [design](…) · [specs](…/tree/<sha>/openspec/changes/<id>/specs) · [tasks](…)

<!-- ai-specs:approval-card-scope-end -->
- [ ] I approve exactly this scope (digest 1a2b3c4d)

Approvals for this digest: none yet (1 needed). Only approvers in `openspec/roles.yaml` can approve.
<status line, for example: "Your tick was undone: the scope changed since this card was drawn. Review it again.">
```
Rules:
- Everything above `<!-- ai-specs:approval-card-scope-end -->` is the **scope section**. It depends only on the
  commit, the change folder, the issue number and the repo URL, so two renders of the same head are byte-identical.
- The checkbox line, the approvals line and the status line are the **status section**.
- Text from the proposal is inserted as Markdown, but HTML comments (`<!--`, `-->`) are stripped from it first, so
  a proposal cannot forge a marker or end the scope section early.
- Sensitive paths come from a fixed kit list matched against backticked paths in proposal, design and tasks:
  - `.github/workflows/`, `.github/CODEOWNERS`, `CODEOWNERS`;
  - `openspec/roles.yaml`, `openspec/config.yaml`;
  - `contracts/`, `scripts/` of the kit.

  This adds no `roles.yaml` key: its parser is strict and repos would break.
- The whole card is capped at 60 000 characters (GitHub's limit is 65 536). The requirements line is cut first, with
  "and N more".

## 2. The tick

`issue_comment: edited` runs the review job only when all of these hold:
- `github.event.issue.pull_request` is empty;
- the comment author is `github-actions[bot]`;
- the body starts with the card marker;
- the sender's type is not `Bot`.

Edits made with `GITHUB_TOKEN` do not trigger workflows, so the workflow never reacts to itself.

`card review` reads the event file and decides in this order. The first failure undoes the tick and writes the
reason into the status section.

1. The edited comment is the sticky card. Otherwise: "use the first card".
2. The issue is open, labelled `type:change`, and its block still names the same change and branch.
3. The box is ticked. An unticked edit, or any edit that did not tick, just re-renders the card.
4. `sender.login` (from the event, set by GitHub) is in `approvers`. Otherwise: "@x is not an approver of this
   repo".
5. The workflow fetches the branch head and computes `approval.digest` of the change folder there. The digest in
   the card marker must equal it. Otherwise: "the scope changed since this card was drawn".
6. The edited scope section must equal a fresh render at that head, byte for byte. Otherwise: "the card text was
   changed; it has been restored". This stops anyone with write access from rewording the card to mislead the
   approver while keeping a valid digest.
7. If a valid record for (digest, sender) already exists, nothing is posted (idempotent). Otherwise the workflow
   posts the record:
   ```
   <!-- ai-specs:approval digest=sha256:<hex> commit=<head sha> by=<sender> via=card run=<GITHUB_RUN_ID> -->
   Approved by @<sender> from the approval card: change `<id>` at `<sha12>` (digest `<8>`).
   If you did not tick this box, delete this comment: the approval then no longer counts.
   ```
   The @mention makes GitHub notify the approver of every card approval given in their name.
8. Reconcile:
   - count valid approvals of the current digest with the same function `check-approval` uses;
   - set `state:approved` when the count reaches `min_approvals`, and leave the label alone otherwise;
   - re-render the card unchecked, listing the approvers so far ("1 of 2: @a").

   The next approver ticks the same fresh box.

### Concurrency and idempotency
- **Render runs** (`issues`, `push`) share the concurrency group `ai-specs-card-render-<repo>-<issue or ref>` with
  `cancel-in-progress: true`. Dropping an older render is safe because a newer render reads a newer head.
- **Review runs** have **no** concurrency group. GitHub cancels pending runs in a group, and a cancelled tick would
  lose its sender. Their writes are safe without one:
  - records are append-only and deduplicated per (digest, login); a duplicate from a race counts once;
  - every review run re-renders from the head it read, and step 5 rejects a tick on a card drawn for an older head,
    so a late write can show a stale card but can never approve a stale scope;
  - after writing the label, the run recounts once more. If the count changed meanwhile (another approver's record
    landed), it writes the label again. The label is derived state; `check-approval` stays the authority.

## 3. What makes a card record count (`check-approval`)
For each comment matching the card record pattern, all of these must hold:
- **Author:** `user.login == "github-actions[bot]"` and `user.type == "Bot"`. The `[bot]` suffix is reserved for
  GitHub Apps, and only a workflow's `GITHUB_TOKEN` writes as this one.
- **Unedited:** `created_at == updated_at`. Anyone with write access can edit a bot comment, so an edited record
  proves nothing. The same rule now applies to terminal records.
- **Run:** `GET repos/{owner}/{repo}/actions/runs/<run>` returns a run of this repository with:
  - `event == "issue_comment"`;
  - `path == ".github/workflows/ai-specs-approval.yml"`;
  - `head_branch` equal to the repo's default branch (read from `GET repos/{owner}/{repo}`);
  - `triggering_actor.login == by`;
  - `created_at` not after the comment's `created_at`.
- **Role:** `by` is in `approvers`.

Why this proves the record came from the card workflow:
- Any branch can carry a workflow that writes as `github-actions[bot]`, but only for events such as `push`,
  `workflow_dispatch` or `pull_request`.
- An `issue_comment` run always executes the workflow file of the default branch. That branch is protected and
  changes only through a PR that passes this same approval gate and a review.
- So a forged record needs either a run that the event and path checks reject, or a reviewed change to `develop`.

A missing run (deleted, or wrong repo) makes the record not count, with exit 1 and "approve again". An API failure is
exit 2, as today.

Terminal records keep their format and rules (author equals `by`), plus the new "unedited" rule. Card and terminal
approvals count together, by distinct login.

## 4. Security model, stated plainly
| Threat | Covered by | Residual |
|---|---|---|
| A non-approver ticks the box | sender check (step 4) | none |
| Someone rewrites the card text to mislead | step 6 restores it; approval binds to the head digest | none |
| The head moves between reading and ticking | step 5 | none |
| A forged `via=card` record from a branch workflow | event, path and default-branch checks | a reviewed, approved PR that adds such a workflow to `develop` |
| A record edited later to a new digest | unedited rule | none |
| Workflow script injection from issue, branch or comment text | values only through env and the event file; strict regexes; no `${{ }}` of them in `run:` | none known |
| A compromised action or kit tag | every `uses:` and the kit checkout pinned to commit SHAs | an update must re-pin |
| **An agent ticks the box, or posts a marker, with the owner's token** | GitHub cannot tell it from the owner, nor can the workflow. The boundary is the AI-HQ guard: change `approval-guard` in ai-hq (HQ-118) denies those commands. Every card approval @mentions the approver (detection). | Paths the guard does not see: a script file the agent writes and runs, a browser driven by an agent, a GitHub MCP server with write tools. They stay out of scope here; the owner should not give agents such tools. |

The same agent risk exists today for terminal approvals: `gh api … -f body='<!-- ai-specs:approval … -->'`. The
guard change closes both.

## 5. Kit 0.3.0 and the workflow file
`kit/approval-card.yml.tmpl` becomes `.github/workflows/ai-specs-approval.yml`. Outline:
```yaml
# ai-specs:workflow version={{VERSION}}
name: ai-specs-approval
on:
  issues: {types: [opened, edited, reopened]}
  issue_comment: {types: [edited]}
  push: {branches: ['change/**']}
permissions: {contents: read, issues: write}
jobs:
  render:   # issues, push; concurrency group per issue/ref, cancel-in-progress
  review:   # issue_comment on the card, sender not a bot; no concurrency group
# Each job:
#   checkout of the kit at {{KIT_SHA}}             # v{{VERSION}}
#   setup-python 3.12
#   `card resolve`: validates the issue and branch, writes them to $GITHUB_OUTPUT
#   checkout of `steps.resolve.outputs.branch` into change-src/ (persist-credentials: false, fetch-depth: 1)
#   `card render` or `card review`, with GH_TOKEN, GH_REPO and GITHUB_EVENT_PATH; GITHUB_RUN_ID from the runner
```
Rules:
- **Pins.** `actions/checkout` and `actions/setup-python` are pinned by full SHA with the version in a comment.
  At the time of writing: `actions/checkout@11bd71901bbe5b1630ceea73d27597364c9af683 # v4.2.2` and
  `actions/setup-python@a26af69be951a213d495a4c3e4e4022e16d87065 # v5.6.0`; the implementation re-checks them.
  `ai-specs.yml` gets the same pins.
- **Kit ref.** `init` resolves `{{KIT_SHA}}` with `git -C <kit> rev-parse v<VERSION>^{commit}` and refuses when the
  tag is missing. The kit repo is public, so no `AI_SPECS_TOKEN` is used by the new workflow.
- **Self mode.** In the kit repo itself, the kit checkout is removed and `scripts/` is used, as `ai-specs.yml` does
  today.
- **Change branch is data.** The workflow only reads the change folder from `change-src/` (plain files plus `git
  rev-parse HEAD`). Nothing in it is executed or imported.
- **`ai-specs.yml`.** The `approval` job adds `actions: read` for the run lookup. Nothing else changes.

`push` events run the workflow file of the pushed branch. A branch may therefore carry a modified card workflow. It
can at most write comments and labels: labels are advisory, and its records fail the run checks of section 3.

## 6. Rollout
1. **The guard first.** The ai-hq change `approval-guard` (HQ-118) is approved, merged and installed on the
   machine (`install.sh` re-links the hooks) before `v0.3.0` is tagged.
2. **ai-specs adopts itself in this PR.** Task 6.2 re-runs `init .` in self mode, so the card workflow lands in
   `develop` with this change. `issue_comment` and `issues` events use the default branch's file, so the card is live
   on ai-specs right after merge.
3. **Tag.** Release `develop → pre-production → production`, then tag `v0.3.0`.
4. **Other repos.** How kit updates land today: the repo re-runs `init` (ADR-0003, ADR-0004), and the regenerated
   files go through a PR into `develop`, which needs the `approval` check. LangBrain took kit 0.2.1 inside the
   audit-fixes change. There is no exemption: a kit bump rewrites `.github/workflows/`, the very files that enforce
   approval, so it must stay approved. The least-friction compliant path is one size-S `type:change` per repo, "adopt
   ai-specs kit 0.3.0":
   - its only task is `init` plus the repo gate;
   - it is approved once in the terminal, since the card is not live there until that PR merges;
   - every later change in that repo can use the card.

   Rejected alternatives:
   - Folding the bump into an open change, such as ai-hq #32, which is already approved and whose spec is merged:
     that would reopen an approved scope.
   - Cross-repo approval, where an ai-specs issue would approve another repo's PR: new trust rules for one PR each.
5. **`doctor`** lists repos whose card workflow is missing or older than the kit.

Steps 3 and 4 happen after this change is archived and merged, so they are not tasks here: the release follows
section 9 of the standard, and each adoption has its own issue.

## 7. Compatibility and migration
- Repos on kit 0.2.x keep working. Their `check-approval` ignores `via=card` records, because the old regex expects
  `-->` right after `by=`. A card approval therefore cannot pass an old gate by accident.
- The new "unedited" rule could invalidate an existing approval comment that someone edited. None exists in the
  three repos today (checked at implementation, task 2.1). An affected change is approved again.
- Branch protection, required checks and `roles.yaml` are unchanged.

## 8. Test strategy
- **Unit, render** (`tests/test_card.py::RenderTest`):
  - section extraction and truncation;
  - stripping of HTML comments from the proposal;
  - links at the commit;
  - human-gate tasks and sensitive paths;
  - determinism (two renders are identical);
  - the size cap.
- **Unit, render and review against `tests/fake_gh.py`** (extended with comment PATCH, `created_at`/`updated_at`,
  the repo's default branch and `actions/runs/<id>`), in `SyncTest` and `ReviewTest`:
  - every acceptance and refusal path of section 2;
  - idempotency;
  - `min_approvals` 2;
  - the post-label recount.
- **Unit, check** (`tests/test_approval.py::CardRecordTest`):
  - each condition of section 3 failing on its own;
  - mixed terminal and card approvals;
  - a missing run is exit 1;
  - an API failure is exit 2.
- **Workflow template** (`tests/test_ai_specs.py::CardWorkflowTest`):
  - exact permissions;
  - every `uses:` pinned to 40 hex;
  - the kit ref is a SHA;
  - no `${{ github.event.* }}` inside any `run:`;
  - job conditions;
  - self mode.
- **e2e** (`scripts/e2e.sh`): in a scratch repo, it renders a card from a real git branch, ticks it through the fake
  `gh` as an approver, and passes `check-approval --pr`. Then it edits the proposal, re-renders, and `check-approval`
  exits 1.
- **Behavioural check by a person** (task 6.3), before merge, on a throwaway private repo whose default branch is this
  change's branch (self mode, so the card runs this commit's scripts); it also confirms the run fields of section 3
  on a real run:
  1. Open a throwaway S change and push its branch. The card appears.
  2. Tick it from the GitHub mobile app. The record and `state:approved` appear, and a notification arrives.
  3. Push a wording edit. The card comes back unchecked and the issue returns to `state:proposed`.
  4. Delete the throwaway repo.

## Change impact
| Changed (symbol / endpoint / table / event) | Used by today | Breaks? | Mitigation / rollback |
|---|---|---|---|
| New workflow `.github/workflows/ai-specs-approval.yml` (issues: write) | nobody yet | No | remove the file (re-run `init` with kit 0.2.2) |
| Approval record `via=card run=<id>` | `check-approval` 0.3.0 | No; old kits ignore it (fail closed) | approve in the terminal |
| `check-approval` ignores edited approval comments | CI `approval` job, AI-HQ and LangBrain builders (via `check-approval`) | Only for an edited approval comment (none known) | approve again |
| `ai-specs.yml` `approval` job adds `actions: read` | CI | No | revert |
| Kit workflows pinned by SHA, kit checkout pinned to the tag commit | CI of adopting repos | No; same code as the tag | re-run `init` |
| `init` writes a second workflow; `doctor` reports it | owner, AI-HQ `/hq-spec` | No | revert |
| Issue state automatically back to `state:proposed` on a scope change | AI-HQ autopilot and factory (they check approval) | No; they already treat it as unapproved | revert the workflow |
| `VERSION` 0.3.0 and tag `v0.3.0` | `doctor` in every adopting repo (reports kit outdated) | No | keep 0.2.2 in a repo by not re-running `init` |

## Rollback
1. Revert this change's PR in ai-specs.
2. Re-run `init` with kit 0.2.2 in each adopting repo (through their own change), which deletes nothing; then delete
   `.github/workflows/ai-specs-approval.yml` in the same PR.

Effects:
- Card records stay on issues but no longer count. An in-flight change approved only by card is approved again in
  the terminal.
- No data migration is involved.
- The `v0.3.0` tag stays (tags are never rewritten), and a `v0.3.1` revert release is cut if needed.
