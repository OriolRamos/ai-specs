## Purpose

Gives every kind of project knowledge one canonical place so decisions, behaviour and history are never lost.

## ADDED Requirements

### Requirement: ASP-073 — The brain links, it does not define
The standard's memory section SHALL state that specs, ADRs and issues stay canonical for behaviour, decisions and state,
that the brain holds research, attempts, failures, domain context, reasons and lessons, and that a brain page SHALL link
to a spec, ADR or issue instead of restating it; the consolidation SHALL report restated canonical content.

#### Scenario: Standard carries the taxonomy
- **GIVEN** ai-specs at the version that includes this change
- **WHEN** `docs/standard.md` section "Memory" is read
- **THEN** it has the taxonomy table with the brain row and the "links, does not define" rule
- **Proof:** `python3 -m unittest tests.test_ai_specs.StandardMemoryTest` in ai-specs passes
