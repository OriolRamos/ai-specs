## ADDED Requirements

### Requirement: ASP-020 — Change digest
`ai-specs digest <repo> <change>` SHALL print `sha256:<hex>` computed over every file of the change folder sorted by
relative POSIX path, each contributing its path, a NUL byte and its content with CRLF normalised to LF, where in
`tasks.md` every `- [x]` or `- [X]` is read as `- [ ]`. It SHALL find the change in `openspec/changes/<change>/` or,
after archive, in `openspec/changes/archive/*-<change>/`.

#### Scenario: Ticking tasks keeps the digest
- **GIVEN** a change whose digest is D
- **WHEN** task 1.1 is ticked in `tasks.md`
- **THEN** `ai-specs digest` still prints D
- **Proof:** `python3 -m unittest tests.test_approval.DigestTest.test_ticking_tasks_keeps_the_digest` in ai-specs passes

#### Scenario: Editing the scope changes the digest
- **GIVEN** a change whose digest is D
- **WHEN** one word of a requirement in its delta spec changes
- **THEN** `ai-specs digest` prints a value different from D
- **Proof:** `python3 -m unittest tests.test_approval.DigestTest.test_scope_edit_changes_the_digest` in ai-specs passes

#### Scenario: Archived change keeps its digest
- **GIVEN** a change with digest D whose tasks are all ticked
- **WHEN** it is archived with `openspec archive <id> --yes`
- **THEN** `ai-specs digest` on the same id prints D from the archive folder
- **Proof:** `bash scripts/e2e.sh` in ai-specs passes its "digest survives archive" step

### Requirement: ASP-021 — Roles
An adopting repo SHALL have `openspec/roles.yaml` with the lists `approvers`, `reviewers` and `releasers` of GitHub
logins and an integer `min_approvals` of at least 1. `ai-specs lint` SHALL fail when the file is missing, malformed,
has an empty `approvers` list, or `min_approvals` exceeds the number of approvers.

#### Scenario: Missing approvers
- **GIVEN** a repo whose `roles.yaml` has `approvers: []`
- **WHEN** `ai-specs lint` runs
- **THEN** it exits 1 naming `openspec/roles.yaml` and the empty `approvers` list
- **Proof:** `python3 -m unittest tests.test_approval.RolesTest` in ai-specs passes

### Requirement: ASP-022 — Human approval bound to the digest
`ai-specs approve <repo> <issue>` SHALL refuse unless the logged-in `gh` user is in `approvers`, it runs on an
interactive terminal, and the environment variable `CLAUDECODE` is not set; it SHALL show the current digest, require
the person to type its first 8 hexadecimal characters, then post an issue comment containing
`<!-- ai-specs:approval digest=sha256:<hex> commit=<sha> by=<login> -->` and set the issue to `state:approved`.

#### Scenario: Agent session cannot approve
- **GIVEN** an approver logged in to `gh` and `CLAUDECODE=1` in the environment
- **WHEN** `ai-specs approve . 12` runs
- **THEN** it exits 1 with "approval must be given by a person in their own terminal" and posts nothing
- **Proof:** `python3 -m unittest tests.test_approval.ApproveTest.test_agent_session_is_refused` in ai-specs passes

#### Scenario: Non-approver cannot approve
- **GIVEN** a `gh` user not listed in `approvers`
- **WHEN** `ai-specs approve . 12` runs on a terminal
- **THEN** it exits 1 naming the login and the approvers list, and posts nothing
- **Proof:** `python3 -m unittest tests.test_approval.ApproveTest.test_non_approver_is_refused` in ai-specs passes

#### Scenario: Approver approves the exact digest
- **GIVEN** an approver on a terminal, outside an agent session, and a change with digest D
- **WHEN** they run `ai-specs approve . 12` and type the first 8 characters of D
- **THEN** one comment with `digest=D` and `by=<login>` is posted and the issue moves to `state:approved`
- **Proof:** `python3 -m unittest tests.test_approval.ApproveTest.test_approver_posts_digest_and_label` in ai-specs passes

### Requirement: ASP-023 — Approval gate
`ai-specs check-approval <repo> <issue>` (or `--pr <n>`, which reads `Closes #<issue>` from the PR body) SHALL exit 0
only when at least `min_approvals` distinct approvers each have an approval comment, authored by that same login,
whose digest equals the change's current digest; it SHALL exit 1 when approvals are missing or stale, and 2 when it
cannot check. No caller SHALL treat exit 2 as approved.

#### Scenario: Scope edited after approval
- **GIVEN** an approval for digest D and a later commit that edits the proposal
- **WHEN** `ai-specs check-approval . 12` runs
- **THEN** it exits 1 with "approved digest D no longer matches"
- **Proof:** `python3 -m unittest tests.test_approval.CheckTest.test_stale_approval_fails` in ai-specs passes

#### Scenario: Forged approval comment
- **GIVEN** an approval comment with `by=OriolRamos` authored by another login
- **WHEN** `ai-specs check-approval . 12` runs
- **THEN** that comment is ignored and the check exits 1
- **Proof:** `python3 -m unittest tests.test_approval.CheckTest.test_comment_author_must_match` in ai-specs passes

#### Scenario: Factory refuses to start without approval
- **GIVEN** a change issue in `state:proposed`
- **WHEN** `/hq-factory` is asked to build it
- **THEN** it stops before creating any commit and tells the owner to run `/hq-approve`
- **Proof:** `python3 -m unittest tests.test_openspec_mode.FactoryGateTest` in ai-hq passes
