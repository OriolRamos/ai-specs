## Purpose

Defines the checks that must pass before a change merges, from the repo's own gate to a rehearsal of the whole flow.

## ADDED Requirements

### Requirement: ASP-062 — The whole flow is rehearsed
AI-HQ SHALL have an integration test that runs the real ai-hq and ai-specs tools through issue, spec, refused build,
human approval, build, archive with strict validation, PR approval check, scope-edit detection, release, promotion and an
annotated tag, against a simulated GitHub and a real git remote; it SHALL skip only when no `openspec` CLI is available.

#### Scenario: Rehearsal passes
- **GIVEN** ai-specs next to ai-hq and an `openspec` CLI (`OPENSPEC` or on PATH)
- **WHEN** the rehearsal test runs
- **THEN** every step passes and the tag `v0.1.0` is annotated on the remote
- **Proof:** `OPENSPEC=<cli> python3 -m unittest tests.test_flow_rehearsal` in ai-hq passes
