## Purpose

Makes GitHub issues the visible source of truth for the state of every change, from proposal to release.

## ADDED Requirements

### Requirement: ASP-010 — One issue per change
Every OpenSpec change in an adopting repo with a GitHub remote SHALL have exactly one open issue labelled
`type:change` in that repo. The issue body SHALL contain the managed block `<!-- ai-specs:change -->` with the change
id, branch, size, spec commit and digest, and only the tools SHALL rewrite that block.

#### Scenario: Proposing creates the issue and the block
- **GIVEN** a registered repo with `tracker = "github"` and no issue for change `add-greeting`
- **WHEN** `/hq-spec` proposes `add-greeting`
- **THEN** one issue exists with labels `type:change`, `state:proposed` and `size:S`, and its body contains the managed block with `change: add-greeting` and `branch: change/<n>-add-greeting`
- **Proof:** `python3 -m unittest tests.test_tracker.ProposeTest` in ai-hq passes (fake `gh` records the exact calls)

#### Scenario: The block is rewritten, the rest of the body is kept
- **GIVEN** an issue whose body has free text above and below the managed block
- **WHEN** the tracker updates the digest
- **THEN** only the lines between the block markers change
- **Proof:** `python3 -m unittest tests.test_tracker.ManagedBlockTest` in ai-hq passes

### Requirement: ASP-011 — Exactly one state label
A change or epic issue SHALL carry exactly one label among `state:proposed`, `state:approved`, `state:in-progress`,
`state:in-review` and `state:blocked` while open. Moving to a state SHALL remove every other `state:*` label in the
same operation.

#### Scenario: Moving to in-progress
- **GIVEN** an issue labelled `state:approved`
- **WHEN** the tracker moves it to `in-progress`
- **THEN** the issue has `state:in-progress` and no other `state:*` label
- **Proof:** `python3 -m unittest tests.test_tracker.StateTest` in ai-hq passes

### Requirement: ASP-012 — Epics with deliveries as sub-issues
Work that changes more than one repo SHALL have an epic issue labelled `type:epic` in the product's platform repo (or
in the single repo of a one-repo product), and each repo's change issue SHALL be a sub-issue of that epic. The epic
SHALL be closed only when all its sub-issues are closed.

#### Scenario: Two-repo work
- **GIVEN** a product with a platform repo and two repos, and an aligned two-repo change
- **WHEN** `/hq-spec` proposes it
- **THEN** one `type:epic` issue exists in the platform repo with exactly two sub-issues, one `type:change` issue in each repo
- **Proof:** `python3 -m unittest tests.test_tracker.EpicTest` in ai-hq passes

#### Scenario: Epic stays open while a delivery is open
- **GIVEN** an epic with one closed and one open sub-issue
- **WHEN** `/hq-ship` checks the epic
- **THEN** the epic stays open and the open delivery is reported
- **Proof:** `python3 -m unittest tests.test_tracker.EpicTest.test_epic_closes_only_when_all_deliveries_are_closed` in ai-hq passes

### Requirement: ASP-013 — Traceability chain
Every change SHALL be traceable from issue to release: the work branch SHALL be `change/<issue>-<slug>` created from
`develop`; every commit on it SHALL carry the trailer `Refs #<issue>`; the PR into `develop` SHALL contain
`Closes #<issue>` and a link to the change folder; the release PR and the GitHub release SHALL list every issue closed
since the previous tag.

#### Scenario: Release notes list the closed issues
- **GIVEN** two change PRs merged into `develop` with `Closes #12` and `Closes #15` since tag `v0.3.0`
- **WHEN** `/hq-ship release` prepares the release PR
- **THEN** the PR body lists `#12` and `#15` grouped by change type and links each one
- **Proof:** `python3 -m unittest tests.test_ship.ReleaseNotesTest` in ai-hq passes

#### Scenario: Commit without the trailer is flagged
- **GIVEN** a work branch with one commit lacking `Refs #<issue>`
- **WHEN** `/hq-factory` prepares the PR
- **THEN** it stops and names the commit before opening the PR
- **Proof:** `python3 -m unittest tests.test_tracker.TrailerTest` in ai-hq passes
