## Purpose

Gives every kind of project knowledge one canonical place so decisions, behaviour and history are never lost.

## ADDED Requirements

### Requirement: ASP-070 — One canonical place per kind of memory
The standard SHALL define one canonical location per kind of memory: behaviour in `openspec/specs/`; change history in
the archive, closed issues and releases; repo decisions in the repo's `docs/adr/`; cross-repo decisions in the platform
repo's `docs/adr/` (or ai-specs for the method); private notes and lessons in the workspace; regenerable context in
`.agents/memory/`. A decision SHALL NOT live only in the workspace or only in `.agents/memory/`.

#### Scenario: ADR template is provided
- **GIVEN** a repo initialised with kit 0.2
- **WHEN** `ai-specs adr new . "Use develop as default branch"` runs
- **THEN** `docs/adr/0001-use-develop-as-default-branch.md` exists with Status, Context, Decision and Consequences sections
- **Proof:** `python3 -m unittest tests.test_ai_specs.AdrTest` in ai-specs passes

### Requirement: ASP-071 — Lessons become rules through a change
A lesson recorded twice SHALL be proposed as a change to the standard, a skill or the repo's rules through the same
issue and approval flow; no rule SHALL be added to a repo outside a reviewed PR.

#### Scenario: Repeated lesson
- **GIVEN** the same lesson recorded twice in the workspace `lessons-learned.md`
- **WHEN** `/hq-retro` runs
- **THEN** it opens a `type:change` issue in the repo that should hold the rule, in `state:proposed`, quoting both lessons
- **Proof:** `python3 -m unittest tests.test_retro.LessonToChangeTest` in ai-hq passes
