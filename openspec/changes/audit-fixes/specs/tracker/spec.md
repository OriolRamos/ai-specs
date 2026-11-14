## Purpose

Makes GitHub issues the visible source of truth for the state of every change, from proposal to release.

## ADDED Requirements

### Requirement: ASP-014 — Private state repos stay off the approval flow
A repo that only stores private operational state (such as the AI-HQ workspace) SHALL use `tracker = "none"`, work on
`develop` (the agent commits and pushes there directly), keep `main` as its only protected branch in the registry, and
have a format-only gate.

#### Scenario: Workspace registry entry
- **GIVEN** the AI-HQ registry
- **WHEN** the entry `hq-workspace` is read
- **THEN** it has `tracker = "none"`, `default_branch = "develop"`, `protected = ["main"]` and a gate that parses the registry
- **Proof:** `python3 -m unittest tests.test_registry_gate.WorkspaceTest` in ai-hq passes
