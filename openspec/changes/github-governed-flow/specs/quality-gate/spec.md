## ADDED Requirements

### Requirement: ASP-060 — One gate per repo
An adopting repo SHALL declare exactly one gate command in its README and, when registered in AI-HQ, in the registry
field `gate`; the gate SHALL run format check, lint, typecheck where the language has one, and tests, and SHALL exit
non-zero on any failure.

#### Scenario: Registry without a gate
- **GIVEN** a registered repo with `tracker = "github"` and no `gate`
- **WHEN** `registry.py validate` runs
- **THEN** it reports the repo as a gap and exits 1
- **Proof:** `python3 -m unittest tests.test_registry_gate` in ai-hq passes

### Requirement: ASP-061 — Kit workflow and required checks
`ai-specs init` SHALL write `.github/workflows/ai-specs.yml` with the jobs `ai-specs` (OpenSpec strict validation,
ai-specs lint, contract check), `approval` (on pull requests into `develop`: `check-approval --pr`) and `gate` (the
repo's gate command); the workflow SHALL request only `contents: read`, `issues: read` and `pull-requests: read`.

#### Scenario: Workflow is written with least privileges
- **GIVEN** a repo initialised with kit 0.2 and gate `make verify`
- **WHEN** the workflow file is read
- **THEN** it has the three jobs, the gate job runs `make verify`, and its permissions are exactly the three read scopes
- **Proof:** `python3 -m unittest tests.test_ai_specs.WorkflowTest` in ai-specs passes

#### Scenario: PR without approval is blocked by CI
- **GIVEN** a PR into `develop` whose linked issue has no approval for the current digest
- **WHEN** the `approval` job runs
- **THEN** the job fails and branch protection blocks the merge
- **Proof:** the first real change on LangBrain shows a red `approval` check before approval and a green one after, linked from its issue
