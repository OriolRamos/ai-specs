## Purpose
Keeps develop, pre-production and production protected, released by people and traceable from issue to tag.

## MODIFIED Requirements

### Requirement: ASP-035 — The guard follows the registry
For a repo registered in AI-HQ, the guard SHALL treat exactly the registry's `protected` branches as protected (no
commit, merge or push on them by the agent). For any other repo it SHALL protect the base list `main`, `master`,
`develop`, `pre-production`, `production`. It SHALL also protect the branch that `refs/remotes/origin/HEAD` names when
that ref resolves in the local clone. It SHALL read only local git metadata to decide.

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

#### Scenario: Unregistered repos protect develop and their default branch
- **GIVEN** a repo that is not in the registry, on branch `develop`, whose `origin/HEAD` points to `origin/trunk`
- **WHEN** the agent runs `git push origin develop`, `git push` (on `develop`) or `git push origin trunk`
- **THEN** each push is denied, naming the protected branch, and `git push -u origin change/1-x` is allowed
- **Proof:** `python3 -m unittest tests.test_guard_registry.UnregisteredDefaultsTest` in ai-hq passes (AI-HQ change `guard-github-bypasses`)
