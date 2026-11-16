## Purpose

Gives every repo one gate command and a kit workflow whose checks and permissions are fixed by the kit version.

## ADDED Requirements

### Requirement: ASP-119 — Kit 0.3.0 installs and reports the card workflow
`ai-specs init` with kit 0.3.0 SHALL write `.github/workflows/ai-specs-approval.yml` next to `ai-specs.yml`. Both
files SHALL carry `# ai-specs:workflow version=0.3.0` and pin every `uses:` and the kit checkout by commit SHA. In
the kit repo itself, `init` SHALL use `scripts/` from the same commit instead of a kit checkout. The `approval` job
of `ai-specs.yml` SHALL request `actions: read` in addition to its read permissions. `init` SHALL refuse when tag
`v<VERSION>` cannot be resolved in the kit checkout. `ai-specs doctor` SHALL report a card workflow that is missing
or carries an older version.

#### Scenario: Re-running init upgrades a 0.2.2 repo
- **GIVEN** a repo initialised with kit 0.2.2 and a declared gate
- **WHEN** `ai-specs init . --prefix EE` runs with kit 0.3.0
- **THEN** both workflow files exist with `version=0.3.0`, the gate command is kept, the `approval` job has
  `actions: read`, and `ai-specs doctor .` reports no outdated kit
- **Proof:** `python3 -m unittest tests.test_ai_specs.CardWorkflowTest.test_init_upgrades_and_doctor_reports` in ai-specs passes

#### Scenario: Missing tag
- **GIVEN** a kit checkout without tag `v0.3.0`
- **WHEN** `ai-specs init . --prefix EE` runs outside self mode
- **THEN** it exits non-zero with "tag v0.3.0 not found in the kit: fetch tags" and writes no workflow
- **Proof:** `python3 -m unittest tests.test_ai_specs.CardWorkflowTest.test_init_refuses_without_tag` in ai-specs passes
