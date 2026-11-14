## Purpose

Defines the format rules every ai-specs change follows so OpenSpec, the lint and CI accept it from proposal to archive.

## ADDED Requirements

### Requirement: ASP-080 — New capabilities carry their Purpose
Every delta spec SHALL start with a `## Purpose` section; when the capability's living spec
`openspec/specs/<capability>/spec.md` does not exist yet, `ai-specs lint` SHALL fail unless that Purpose has at least
50 characters, so that the archived living spec passes `openspec validate --all --strict`.

#### Scenario: New capability without Purpose
- **GIVEN** a change whose delta creates capability `greeting` and has no `## Purpose`
- **WHEN** `ai-specs lint . <change>` runs
- **THEN** it exits 1 naming `specs/greeting/spec.md` and "new capability needs a ## Purpose of at least 50 characters"
- **Proof:** `python3 -m unittest tests.test_ai_specs.PurposeTest` in ai-specs passes

#### Scenario: Archive of a new capability validates strictly
- **GIVEN** a change with a 50+ character Purpose creating capability `greeting`
- **WHEN** it is archived and `openspec validate --all --strict` runs
- **THEN** the validation exits 0
- **Proof:** `bash scripts/e2e.sh` in ai-specs passes its "validate --all --strict after archive" step
