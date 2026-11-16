**Size:** L

## Why
Today an approver approves a change only with `ai-specs approve` in their own terminal: they read the folder at some
commit, then type the first 8 characters of a digest they cannot read meaningfully. Two problems follow:

1. **Friction.** The owner reviews proposals on the GitHub web and mobile UI, but has to go back to a terminal to
   approve. Approvals wait for a desk.
2. **Opacity.** The digest proves *which bytes* were approved, not *what they say*. Nothing on the issue tells the
   approver, in plain language, what the frozen scope is: why, what changes, what must not be added, which
   requirements, which human-gate tasks, which sensitive paths.

The kit can put that summary on the issue itself, next to a single checkbox, and record a tick of that checkbox as an
approval bound to the same digest. It must not weaken the approval: the boundary is still "only a person in
`approvers` approves the exact digest", and the honest limit (agents act with the owner's GitHub token) is closed on
the machine by the AI-HQ guard, specified in its own change in ai-hq.

## What Changes
- **Approval card (ASP-111, ASP-112).** A new kit workflow, `.github/workflows/ai-specs-approval.yml`, keeps one
  sticky bot comment (marker `<!-- ai-specs:approval-card … -->`) on every open `type:change` issue whose managed
  block names a `change/<issue>-<slug>` branch that exists. It runs on `issues` (opened, edited, reopened) and on
  `push` to `change/**`. The card is rendered from the change folder at the branch head and shows, in plain
  language:
  - the change id, size, issue and branch;
  - Why, What Changes and Not to add from `proposal.md`, each truncated at a fixed length with a link to the full text;
  - the requirement ids and titles of every delta spec, and the number of tasks;
  - the tasks marked `(human gate)` and the sensitive paths the change names;
  - links to proposal, design, specs and tasks at the exact commit;
  - the short digest (8 hex characters) and one checkbox: `- [ ] I approve exactly this scope (digest <8>)`.

  When the digest at the head changes, the card is rewritten unchecked and an issue in `state:approved`,
  `state:in-progress` or `state:in-review` goes back to `state:proposed` (standard section 7 already says so; the
  workflow now does it).
- **One-click approval (ASP-113, ASP-114, ASP-115).** The same workflow runs on `issue_comment: edited` of the card.
  It records an approval only when all of these hold:
  - the editor (`github.event.sender.login`, given by GitHub, never read from comment text) is in `approvers`;
  - the box is ticked, and the rest of the card's scope section is byte-identical to a fresh render at the head;
  - the digest on the card equals the digest recomputed now at the branch head.

  The record is a new bot comment `<!-- ai-specs:approval digest=… commit=… by=<sender> via=card run=<run id> -->`
  that @mentions the approver. The card is re-rendered unchecked with the approvals so far, and `state:approved` is
  set once `min_approvals` distinct approvers approved the current digest. Any other tick is undone and the card
  says why. Records are deduplicated per digest and login, so re-runs and concurrent events are harmless.
- **`check-approval` accepts verified card approvals (ASP-117, ASP-118).** A `via=card` record counts for its `by`
  login only if:
  - it was written by `github-actions[bot]`, which only a workflow's `GITHUB_TOKEN` can do;
  - it was never edited;
  - its `run` exists in this repo with event `issue_comment`, workflow path `.github/workflows/ai-specs-approval.yml`,
    head branch equal to the default branch, and triggering actor equal to `by`.

  An `issue_comment` run always uses the workflow file of the default branch, which only an approved, reviewed PR can
  change. Card and terminal approvals count together by distinct login. An edited approval comment, of either kind,
  no longer counts. `ai-specs approve` in the terminal stays as the fallback, unchanged.
- **Kit 0.3.0 (ASP-116, ASP-119).**
  - `init` writes the card workflow next to `ai-specs.yml`, with the permissions `contents: read` and
    `issues: write` only, and `GITHUB_TOKEN` as its only credential.
  - Every `uses:` in both kit workflows is pinned to a full commit SHA, and the kit checkout is pinned to the commit
    of the `v0.3.0` tag.
  - The `approval` job gains `actions: read` to verify runs.
  - `doctor` reports a missing or outdated card workflow.
  - `VERSION` becomes `0.3.0`, with tag `v0.3.0`.
- **Rollout.**
  1. The ai-hq guard change lands first.
  2. ai-specs adopts the kit through its own `init` in this PR.
  3. ai-hq and LangBrain each get a small `type:change` "adopt kit 0.3.0" that re-runs `init`, approved once in the
     terminal: the card is not live in a repo until that PR merges.
- **Docs.** Standard sections 7, 8, 12 and 15, the agents block, README, ADR-0005 and the ADR index.
- **Excludes:**
  - revoking an approval from the UI (deleting the record comment is the way, as today for terminal approvals);
  - GitHub Environments or PR reviews as the approval mechanism (see design);
  - approving from any surface other than the card and the terminal;
  - a lint rule or `roles.yaml` key change;
  - changing the digest algorithm;
  - auto-merge;
  - notifications other than the @mention in the record;
  - repos with `tracker = "none"`.

## Not to add
- No secret, PAT, GitHub App or signing key: the workflows use `GITHUB_TOKEN` only.
- No permission beyond `contents: read` and `issues: write` on the card workflow, and only `actions: read` added to
  `ai-specs.yml`.
- No trust in any text inside a comment for identity: the approver is `github.event.sender.login`; `by=` in a record
  is checked against the run's triggering actor.
- No execution of code from the change branch: the workflow only reads files from it; the code it runs is the
  pinned kit.
- No `${{ … }}` expansion of issue, comment or branch text inside `run:` scripts: values go through environment
  variables and the event file.
- No second digest implementation: the card and `check-approval` share `approval.digest`.
- No new required check and no change to branch protection: `check-approval` stays the gate.
- No automatic approval, label promotion beyond `state:approved`, or merge from the card.
- No company, product or person names in the kit or the standard.

## Prior art and reuse
| Need | Found | Decision |
|---|---|---|
| Digest of the change folder | `approval.digest`, `change_folder` | **Reuse** unchanged; the card hashes the same folder at the branch head |
| Approver list, `min_approvals` | `approval.read_roles` | **Reuse** |
| Issue block parsing | `approval.change_of`, `BLOCK_RE` | **Extend** with `branch_of` |
| GitHub calls | `ghcli.api`, `comments`, `comment`, `set_state` | **Extend** with comment edit, actions run lookup and the comment's app and edit fields |
| Approval record format | `<!-- ai-specs:approval digest=… commit=… by=… -->` | **Extend** with `via=card run=<id>`; the old regex does not match it, so older kits ignore card records (fail closed) |
| Kit workflow template and `kit-checkout` | `kit/workflow.yml.tmpl`, `cmd_init` self mode | **Extend**: a second template with the same placeholders and self-mode rewrite |
| Sticky bot comment pattern | common in public CI bots (one comment found by a hidden marker, edited in place) | **Reuse the pattern**, written in stdlib Python; no third-party action |
| GitHub Environments with required reviewers | native "Approve" button on web and mobile | **Rejected**: it shows no scope summary, needs paid plans on private repos, and an API call with the owner's token approves it just the same |
| Approving the spec PR with a PR review | native review UI | **Rejected**: GitHub forbids approving your own PR, and agents open PRs with the owner's account |
