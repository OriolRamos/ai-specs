## 0. Approval

- [ ] 0.1 [owner] Approve the scope (the audit's six defects and four minor ones, as listed in the proposal) — test first: n/a — proof: `openspec validate audit-fixes --strict && python3 scripts/ai_specs.py lint . audit-fixes` green (human gate)

## 1. ai-specs kit 0.2.1 (ai-specs repo)

- [ ] 1.1 Purpose: lint rule for new capabilities, scaffold template, kit rule, standard text; Purpose added to the seven deltas of github-governed-flow and its new digest recorded — test first: `tests/test_ai_specs.py::PurposeTest` — proof: `python3 -m unittest tests.test_ai_specs.PurposeTest && python3 scripts/ai_specs.py lint .`
- [ ] 1.2 `issue_of_pr` falls back to `change/<n>-` and `hotfix/<n>-` head branches — test first: `tests/test_approval.py::CheckTest::test_issue_from_branch_name` — proof: `python3 -m unittest tests.test_approval`
- [ ] 1.3 Workflow: approval job skipped for dependabot and renovate PR authors — test first: `tests/test_ai_specs.py::WorkflowTest::test_dependency_bots_skip_only_approval` — proof: `python3 -m unittest tests.test_ai_specs.WorkflowTest`
- [ ] 1.4 e2e: `validate --all --strict` after archive, hotfix-branch approval; ADR index; VERSION 0.2.1 — test first: n/a — proof: `bash scripts/e2e.sh`

## 2. ai-hq

- [ ] 2.1 Skill order spec → tickets → approve → factory; `tracker.py propose --job` records the issue — test first: `tests/test_openspec_mode.py::OrderTest`, `tests/test_tracker.py::JobRecordTest` — proof: `python3 -m unittest tests.test_openspec_mode tests.test_tracker`
- [ ] 2.2 `ship` fetches tags; `repo_setup` requires approval on production; `ci.yml` branches — test first: `tests/test_ship.py::ReleaseTest::test_release_fetches_remote_tags` — proof: `python3 -m unittest tests.test_ship tests.test_repo_setup`
- [ ] 2.3 The flow rehearsal as `tests/test_flow_rehearsal.py` — test first: n/a (it is the test) — proof: `OPENSPEC=<cli> python3 -m unittest tests.test_flow_rehearsal`

## 3. hq-workspace and LangBrain

- [ ] 3.1 hq-workspace on `main`, `tracker = "none"`, no protected branch; ADR-017 — test first: `ai-hq tests/test_registry_gate.py::WorkspaceTest` — proof: `python3 ../ai-hq/scripts/registry.py validate`
- [ ] 3.2 LangBrain `context/approval_gate.py`; autopilot skips unapproved issues; factory preflight requires the approved issue — test first: `tests/test_approval_gate.py` — proof: `bash scripts/gate.sh` in LangBrain (CI)

## 4. Close

- [ ] 4.1 Merge ai-specs, tag `v0.2.1`, then merge ai-hq, hq-workspace, LangBrain; archive this change in a later ai-specs PR once the flow is live — test first: n/a — proof: CI green on the four PRs (human gate)
