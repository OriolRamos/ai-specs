## Purpose

Binds work to a human approval of the exact change scope and makes every path that builds or merges code check it.

## ADDED Requirements

### Requirement: ASP-024 — PR to issue by body or branch
`ai-specs check-approval --pr <n>` SHALL resolve the issue from exactly one `Closes #<issue>` in the PR body or, when the
body closes none, from a head branch named `change/<issue>-<slug>` or `hotfix/<issue>-<slug>`; it SHALL fail when
neither resolves.

#### Scenario: Hotfix back-merge into develop
- **GIVEN** an approved hotfix issue 9 and a PR from `hotfix/9-crash` into `develop` whose body says `Refs #9`
- **WHEN** `ai-specs check-approval . --pr <n>` runs
- **THEN** it checks issue 9 and exits 0
- **Proof:** `python3 -m unittest tests.test_approval.CheckTest.test_issue_from_branch_name` in ai-specs passes

### Requirement: ASP-025 — Dependency bots skip only the approval job
The kit workflow's `approval` job SHALL NOT run for pull requests authored by `dependabot[bot]` or `renovate[bot]`, and
SHALL run for every other pull request into `develop` and from `hotfix/*`; the `ai-specs` and `gate` jobs SHALL run for
all of them.

#### Scenario: Workflow condition
- **GIVEN** a repo initialised with kit 0.2.1
- **WHEN** its workflow is read
- **THEN** the approval job condition excludes exactly those two PR authors and the other jobs have no author condition
- **Proof:** `python3 -m unittest tests.test_ai_specs.WorkflowTest.test_dependency_bots_skip_only_approval` in ai-specs passes

### Requirement: ASP-026 — Every builder checks the approval
Every component that builds code for an issue of a repo that runs ai-specs with `tracker = "github"` (the AI-HQ
factory skill, LangBrain's factory and LangBrain's autopilot) SHALL run `ai-specs check-approval` for that issue first and
SHALL NOT build when it does not exit 0.

#### Scenario: Autopilot meets an unapproved issue
- **GIVEN** LangBrain's autopilot polling an ai-specs repo with issue 12 in `state:proposed`
- **WHEN** it filters eligible issues
- **THEN** issue 12 is skipped with "needs an approved spec" and no worker is dispatched for it
- **Proof:** `pytest tests/test_approval_gate.py -q` in LangBrain passes

#### Scenario: Factory job without the approved issue
- **GIVEN** a LangBrain factory job for an ai-specs repo whose job status records no approved issue for it
- **WHEN** the preflight runs
- **THEN** it raises before preparing any worktree, naming the repo and `/hq-approve`
- **Proof:** `pytest tests/test_approval_gate.py -q` in LangBrain passes

### Requirement: ASP-027 — Spec, tasks, approval, build
The AI-HQ skills SHALL lead from `/hq-spec` to `/hq-tickets` to `/hq-approve` to `/hq-factory`, so tasks are part of the
approved digest; `tracker.py propose --job <id>` SHALL record the issue in the job's `status.json` under
`openspec.issues.<repo>`.

#### Scenario: Skill order and job record
- **GIVEN** the AI-HQ skills and a job created with `--openspec`
- **WHEN** `/hq-spec` proposes the change with `tracker.py propose … --job <id>`
- **THEN** `/hq-spec` ends by proposing `/hq-tickets`, `/hq-tickets` by proposing `/hq-approve`, and the job records the issue number
- **Proof:** `python3 -m unittest tests.test_openspec_mode.OrderTest tests.test_tracker.JobRecordTest` in ai-hq passes
