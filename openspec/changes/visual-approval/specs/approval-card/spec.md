## Purpose

Lets an approver see, on the change's GitHub issue and in plain language, exactly what a digest stands for, and
approve that digest with one tick that the kit workflow verifies and records.

## ADDED Requirements

### Requirement: ASP-111 — The card shows exactly what would be approved
The kit workflow SHALL keep one sticky comment by `github-actions[bot]` on each open `type:change` issue whose block
names an existing `change/<issue>-<slug>` branch, rendered only from the change folder at that branch head, the
issue number and the repo URL. It SHALL carry the marker
`<!-- ai-specs:approval-card change=<id> issue=<n> digest=<digest> commit=<sha> -->` and show:
- the change id and size;
- Why, What Changes and Not to add, each truncated at a fixed length with a link to the full text;
- every requirement id and title, the task count, and the human-gate tasks;
- the sensitive paths named;
- links to the artifacts at the commit;
- the 8-character digest and the line `- [ ] I approve exactly this scope (digest <8>)`.

HTML comments in the proposal SHALL be stripped from the card, and two renders of the same head SHALL be
byte-identical.

#### Scenario: Card for a pushed change
- **GIVEN** issue 12 with block `change: demo`, `branch: change/12-demo` and a pushed branch whose folder has digest D
- **WHEN** the card is rendered
- **THEN** the issue has exactly one card comment whose marker holds D and the head SHA, whose links point at
  `blob/<sha>/openspec/changes/demo/`, and whose last scope line is `- [ ] I approve exactly this scope (digest <first 8 of D>)`
- **Proof:** `python3 -m unittest tests.test_card.RenderTest tests.test_card.SyncTest.test_first_render_posts_one_card` in ai-specs passes

#### Scenario: A proposal cannot forge a marker
- **GIVEN** a proposal whose Why contains `<!-- ai-specs:approval-card-scope-end -->` and `<!-- ai-specs:approval … -->`
- **WHEN** the card is rendered
- **THEN** neither string appears in the card body, and the scope section ends at the kit's own end marker
- **Proof:** `python3 -m unittest tests.test_card.RenderTest.test_html_comments_are_stripped` in ai-specs passes

### Requirement: ASP-112 — The card follows the branch head
On `issues` opened, edited or reopened and on `push` to `change/**`, the workflow SHALL re-render the sticky card
from the current head. When the digest differs from the card's, the card SHALL be rewritten unchecked, and an issue
labelled `state:approved`, `state:in-progress` or `state:in-review` SHALL move to `state:proposed`. It SHALL write
nothing in any of these cases:
- the issue is closed;
- the block is missing;
- the branch does not match `^change/<issue>-[a-z0-9][a-z0-9-]*$`;
- the change id is invalid;
- the branch or the folder does not exist;
- a pushed branch is not the one its issue's block names.

#### Scenario: Scope edited after approval
- **GIVEN** issue 12 in `state:approved` for digest D and a push that rewords the proposal (new digest E)
- **WHEN** the push run finishes
- **THEN** the card's marker holds E, its box is unchecked, and the issue's only state label is `state:proposed`
- **Proof:** `python3 -m unittest tests.test_card.SyncTest.test_new_digest_resets_card_and_state` in ai-specs passes

#### Scenario: Ticking tasks during the build changes nothing
- **GIVEN** issue 12 in `state:in-progress` and a push that only ticks tasks in `tasks.md`
- **WHEN** the push run finishes
- **THEN** the card body is unchanged and the label is still `state:in-progress`
- **Proof:** `python3 -m unittest tests.test_card.SyncTest.test_ticked_tasks_keep_card_and_state` in ai-specs passes

#### Scenario: Branch not pushed yet
- **GIVEN** a newly opened issue 13 whose block names `change/13-demo`, which does not exist
- **WHEN** the issues run finishes
- **THEN** no comment is posted and no label changes
- **Proof:** `python3 -m unittest tests.test_card.SyncTest.test_missing_branch_writes_nothing` in ai-specs passes

### Requirement: ASP-113 — A tick by an approver records the approval
On `issue_comment: edited` of the sticky card by a non-bot sender, the workflow SHALL record an approval only when
all of these hold:
- the box is ticked;
- `github.event.sender.login` is in `approvers`;
- the card's digest equals the digest recomputed at the branch head at that moment;
- the edited scope section is byte-identical to a fresh render at that head.

Recording means posting
`<!-- ai-specs:approval digest=<digest> commit=<head> by=<sender> via=card run=<GITHUB_RUN_ID> -->` with an
@mention of the sender, then re-rendering the card unchecked with the approvals so far. `state:approved` SHALL be set
once `min_approvals` distinct approvers have valid approvals for the current digest.

#### Scenario: Owner approves from the phone
- **GIVEN** `roles.yaml` with `approvers: [owner]`, `min_approvals: 1`, and the card for digest D at the head
- **WHEN** `owner` ticks the box
- **THEN** one record comment with `digest=D by=owner via=card run=<id>` and `@owner` is posted, the issue is
  `state:approved`, the card is unchecked and says "Approvals for this digest: @owner (1 of 1)", and
  `ai-specs check-approval . 12` exits 0
- **Proof:** `python3 -m unittest tests.test_card.ReviewTest.test_approver_tick_records_and_approves` in ai-specs passes

#### Scenario: Two approvers needed
- **GIVEN** `approvers: [a, b]`, `min_approvals: 2`, and no approvals yet
- **WHEN** `a` ticks, then `b` ticks the re-rendered card
- **THEN** after the first tick the issue is still `state:proposed` and the card says "1 of 2: @a"; after the second
  it is `state:approved` with two records
- **Proof:** `python3 -m unittest tests.test_card.ReviewTest.test_min_approvals_two` in ai-specs passes

### Requirement: ASP-114 — A tick that cannot be accepted is undone and explained
When a tick fails any condition of ASP-113, or lands on a card that is not the sticky one, or lands on a closed or
non-`type:change` issue, the workflow SHALL post no record and change no label. It SHALL re-render the card unchecked
from the current head, with a status line naming the reason:
- not an approver;
- the scope changed since the card was drawn;
- the card text was changed;
- use the first card;
- the issue is not an open change.

#### Scenario: Non-approver ticks
- **GIVEN** the card for digest D and a sender `someone` not in `approvers`
- **WHEN** `someone` ticks the box
- **THEN** no record is posted, the box is unchecked, and the status line says "@someone is not an approver of this repo"
- **Proof:** `python3 -m unittest tests.test_card.ReviewTest.test_non_approver_is_undone` in ai-specs passes

#### Scenario: Head moved before the tick
- **GIVEN** a card drawn for digest D and a branch head whose digest is now E
- **WHEN** an approver ticks the box
- **THEN** no record is posted, and the card is re-rendered unchecked for E with "the scope changed since this card was drawn"
- **Proof:** `python3 -m unittest tests.test_card.ReviewTest.test_stale_card_is_undone` in ai-specs passes

#### Scenario: Card text altered with the tick
- **GIVEN** the card for the head digest whose Why text was edited by someone, and the box ticked by an approver
- **WHEN** the review runs
- **THEN** no record is posted, and the original scope section is restored unchecked with "the card text was changed"
- **Proof:** `python3 -m unittest tests.test_card.ReviewTest.test_altered_card_is_restored` in ai-specs passes

### Requirement: ASP-115 — Card approvals are idempotent under repeated and concurrent events
The workflow SHALL post at most one record per (digest, login) when a valid one already exists. It SHALL derive the
state label from a recount of valid approvals after writing, recounting once more when the comments changed in
between. Review runs SHALL NOT use a concurrency group that can cancel a pending run.

#### Scenario: Run re-run
- **GIVEN** an approval already recorded for (D, owner)
- **WHEN** the same review run is re-run
- **THEN** no second record is posted and the label stays `state:approved`
- **Proof:** `python3 -m unittest tests.test_card.ReviewTest.test_rerun_is_idempotent` in ai-specs passes

#### Scenario: Two reviews race on the label
- **GIVEN** `min_approvals: 2` and review runs for `a` and `b` whose recounts interleave so that `a` would write `state:proposed` last
- **WHEN** both finish
- **THEN** the issue ends `state:approved`
- **Proof:** `python3 -m unittest tests.test_card.ReviewTest.test_label_recount_after_race` in ai-specs passes

### Requirement: ASP-116 — The card workflow is least-privilege and pinned
`.github/workflows/ai-specs-approval.yml` SHALL request exactly `contents: read` and `issues: write`, SHALL use no
credential other than `GITHUB_TOKEN`, and SHALL pin every `uses:` to a 40-hex commit SHA. Outside self mode, it SHALL
check out the kit at the commit of tag `v<VERSION>`. It SHALL never expand issue, comment or branch text with
`${{ }}` inside a `run:` script, SHALL check out the change branch with `persist-credentials: false`, and SHALL
execute no file from it.

#### Scenario: Template audit
- **GIVEN** a repo initialised with kit 0.3.0
- **WHEN** `.github/workflows/ai-specs-approval.yml` is parsed
- **THEN** permissions are exactly `{contents: read, issues: write}`, every `uses:` ends in `@` + 40 hex, no `run:`
  contains `${{ github.event`, no `secrets.` reference exists, and the kit checkout `ref` is the SHA of `v0.3.0`
- **Proof:** `python3 -m unittest tests.test_ai_specs.CardWorkflowTest` in ai-specs passes
