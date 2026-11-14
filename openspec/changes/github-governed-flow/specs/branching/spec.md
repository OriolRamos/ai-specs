## Purpose

Keeps develop, pre-production and production protected, released by people and traceable from issue to tag.

## ADDED Requirements

### Requirement: ASP-030 — Three protected branches
An adopting repo SHALL have the long-lived branches `develop` (default), `pre-production` and `production`; none of
them SHALL accept direct pushes; `develop` SHALL accept only PRs from `change/*` or `hotfix/*` branches,
`pre-production` only from `develop` or `hotfix/*`, and `production` only from `pre-production` or `hotfix/*`; each
SHALL require the `ai-specs` and `gate` checks, and `develop` also the `approval` check.

#### Scenario: Setup plan for a repo that only has main
- **GIVEN** a GitHub repo with only `main` and no protections
- **WHEN** `repo_setup.py <repo>` runs without `--apply`
- **THEN** it prints, in order, creating `develop` and `pre-production` from `main`, renaming `main` to `production`, making `develop` default, the three protections with their required checks, the labels, `roles.yaml`, CODEOWNERS and the workflow, and changes nothing
- **Proof:** `python3 -m unittest tests.test_repo_setup.PlanTest` in ai-hq passes (fake `gh` records zero mutating calls)

#### Scenario: Applying twice changes nothing the second time
- **GIVEN** a repo already set up
- **WHEN** `repo_setup.py <repo> --apply` runs again
- **THEN** it reports every item as already in place and makes no mutating call
- **Proof:** `python3 -m unittest tests.test_repo_setup.IdempotentTest` in ai-hq passes

### Requirement: ASP-031 — Releases and promotions
A release SHALL be a PR from `develop` to `pre-production` whose body is the changelog since the last tag; a promotion
SHALL be a PR from `pre-production` to `production`; after the promotion is merged by a releaser, an annotated tag
`vX.Y.Z` SHALL be created on `production` and a GitHub release published with the same notes. Agents SHALL only
prepare these PRs and tags, never merge them.

#### Scenario: Promotion is tagged after the human merge
- **GIVEN** a merged promotion PR into `production` for version `0.4.0`
- **WHEN** `/hq-ship tag` runs
- **THEN** an annotated tag `v0.4.0` points at the merge commit and a GitHub release `v0.4.0` lists the issues of the release
- **Proof:** `python3 -m unittest tests.test_ship.TagTest` in ai-hq passes

#### Scenario: Unmerged promotion is not tagged
- **GIVEN** an open promotion PR
- **WHEN** `/hq-ship tag` runs
- **THEN** it creates no tag and says the PR must be merged by a releaser first
- **Proof:** `python3 -m unittest tests.test_ship.TagTest.test_open_pr_is_not_tagged` in ai-hq passes

### Requirement: ASP-032 — Hotfix path
A hotfix SHALL branch from `production` as `hotfix/<issue>-<slug>`, ship through a PR into `production`, and SHALL be
merged back into `pre-production` and `develop` through PRs before the hotfix issue is closed.

#### Scenario: Hotfix back-merge is required
- **GIVEN** a hotfix merged into `production` but not into `develop`
- **WHEN** `/hq-ship` checks the hotfix issue
- **THEN** it keeps the issue open and prepares the back-merge PRs into `pre-production` and `develop`
- **Proof:** `python3 -m unittest tests.test_ship.HotfixTest` in ai-hq passes
