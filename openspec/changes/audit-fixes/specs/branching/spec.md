## Purpose

Keeps develop, pre-production and production protected, released by people and traceable from issue to tag.

## ADDED Requirements

### Requirement: ASP-033 — Approval on production for hotfixes
`production` SHALL require the `approval` check besides `ai-specs` and `gate`; the check runs for `hotfix/*` heads and
reports success when skipped for promotion PRs from `pre-production`.

#### Scenario: Setup plan for production
- **GIVEN** a repo being set up
- **WHEN** `repo_setup.py` plans the protection of `production`
- **THEN** the required checks are `ai-specs`, `approval` and `gate`
- **Proof:** `python3 -m unittest tests.test_repo_setup.IdempotentTest` in ai-hq passes

### Requirement: ASP-034 — Release notes start from the remote's last tag
`ship.py release` and `ship.py promote` SHALL fetch tags from `origin` before computing what changed since the last
`vX.Y.Z` tag.

#### Scenario: Tag only on the remote
- **GIVEN** a tag `v0.3.0` that exists on `origin` but not in the local clone
- **WHEN** `ship.py release` runs
- **THEN** it fetches tags first and the notes say "Changes since v0.3.0"
- **Proof:** `python3 -m unittest tests.test_ship.ReleaseTest.test_release_fetches_remote_tags` in ai-hq passes
