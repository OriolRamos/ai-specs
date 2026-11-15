# branching Specification

## Purpose
Keeps develop, pre-production and production protected, released by people and traceable from issue to tag.

## Requirements

### Requirement: ASP-035 — The guard follows the registry
For a repo registered in AI-HQ, the guard SHALL treat exactly the registry's `protected` branches as protected (no
commit, merge or push on them by the agent); for any other repo it SHALL keep the base list `main`, `master`,
`pre-production`, `production`.

#### Scenario: Workspace develop is writable, main is not
- **GIVEN** the registered workspace with `protected = ["main"]`
- **WHEN** the agent runs `git push origin develop` and then `git push origin main` in it
- **THEN** the first is allowed and the second is denied
- **Proof:** `python3 -m unittest tests.test_guard_registry.RegistryProtectedTest` in ai-hq passes

#### Scenario: Unregistered repos keep the base list
- **GIVEN** a repo that is not in the registry
- **WHEN** the agent runs `git push origin main`
- **THEN** the push is denied as before
- **Proof:** `python3 -m unittest tests.test_guard_registry.RegistryProtectedTest.test_unregistered_keeps_base` in ai-hq passes
