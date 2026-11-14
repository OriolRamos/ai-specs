## 0. Approval and baseline

- [x] 0.1 [owner] Review and approve this change (proposal, design, the seven delta specs, tasks) — test first: n/a — proof: `openspec validate github-governed-flow --strict && python3 scripts/ai_specs.py lint . github-governed-flow` green on the reviewed commit (human gate)
- [ ] 0.2 [owner] Install and log in the GitHub CLI on this machine — test first: n/a — proof: `gh auth status` shows the owner's login with `repo` and `workflow` scopes (human gate)
- [ ] 0.3 [all five repos] Record the baseline: each repo's tests and lint on its current default branch — test first: n/a — proof: outputs pasted in the epic issue once it exists

## 1. ai-specs 0.2 · approval (ai-specs repo)

- [x] 1.1 Digest: `ai-specs digest` with checkbox and CRLF normalisation, live or archived folder — test first: `tests/test_approval.py::DigestTest` — proof: `python3 -m unittest tests.test_approval.DigestTest`
- [x] 1.2 Roles: stdlib reader for `openspec/roles.yaml`, lint rule, `init` writes a default with the given owner — test first: `tests/test_approval.py::RolesTest` — proof: `python3 -m unittest tests.test_approval.RolesTest`
- [x] 1.3 `approve`: gh identity, approvers check, TTY and `CLAUDECODE` refusal, typed confirmation, comment and label — test first: `tests/test_approval.py::ApproveTest` (fake `gh` on PATH) — proof: `python3 -m unittest tests.test_approval.ApproveTest`
- [x] 1.4 `check-approval` by issue or `--pr`: author must match, `min_approvals`, stale digest, exit codes 0/1/2 — test first: `tests/test_approval.py::CheckTest` — proof: `python3 -m unittest tests.test_approval.CheckTest`

## 2. ai-specs 0.2 · contracts, catalog, gate, memory (ai-specs repo)

- [ ] 2.1 `contract new` and `contract check` (pinned ajv-cli and redocly through npx; runner injectable) — test first: `tests/test_contracts.py::NewTest`, `CheckTest` — proof: `python3 -m unittest tests.test_contracts`
- [ ] 2.2 Released contract immutability in `lint` (compares with `origin/production`) — test first: `tests/test_contracts.py::ImmutableTest` — proof: `python3 -m unittest tests.test_contracts.ImmutableTest`
- [ ] 2.3 `init --platform`, `catalog check`, `impact` — test first: `tests/test_catalog.py` — proof: `python3 -m unittest tests.test_catalog`
- [ ] 2.4 Kit workflow `.github/workflows/ai-specs.yml` written by `init` with least privileges and the repo's gate — test first: `tests/test_ai_specs.py::WorkflowTest` — proof: `python3 -m unittest tests.test_ai_specs.WorkflowTest`
- [ ] 2.5 `adr new` and the memory rule in the standard — test first: `tests/test_ai_specs.py::AdrTest` — proof: `python3 -m unittest tests.test_ai_specs.AdrTest`
- [ ] 2.6 Standard 0.2 (`docs/standard.md`), kit config rules, AGENTS block, lint 0.1/0.2 compatibility, `VERSION` 0.2.0, ADR-0002 — test first: `tests/test_ai_specs.py::CompatibilityTest` — proof: `python3 -m unittest discover -s tests`
- [ ] 2.7 Extend `scripts/e2e.sh` with digest-survives-archive, approval with fake gh, contract conformance — test first: n/a — proof: `bash scripts/e2e.sh`

## 3. AI-HQ on the flow (ai-hq repo)

- [ ] 3.1 `scripts/tracker.py`: github backend over `gh` and null backend; managed block, states, epics with sub-issues, trailers — test first: `tests/test_tracker.py` — proof: `python3 -m unittest tests.test_tracker`
- [ ] 3.2 Registry fields `tracker`, `gate`, `product`; validate gap when a github repo has no gate — test first: `tests/test_registry_gate.py` — proof: `python3 -m unittest tests.test_registry_gate`
- [ ] 3.3 `scripts/repo_setup.py`: dry-run plan, `--apply`, `--undo`, idempotent (labels, branches, rename, default, protections, roles, CODEOWNERS, workflow) — test first: `tests/test_repo_setup.py` — proof: `python3 -m unittest tests.test_repo_setup`
- [ ] 3.4 Skills: `/hq-spec` (issue + branch + propose), new `/hq-approve`, `/hq-factory` gate and PR, `/hq-ship` release/promote/tag/hotfix, `/hq-status` and `/hq-triage` from issues, `/hq-retro` lessons to change issues; `docs/openspec-mode.md` rewritten as the GitHub flow — test first: `tests/test_openspec_mode.py::FactoryGateTest`, `tests/test_ship.py`, `tests/test_retro.py` — proof: `python3 -m unittest discover -s tests && python3 scripts/lint_skills.py`
- [ ] 3.5 `prereqs.py`: `gh` required for `hq`, `gh auth status` reported by `hq up`; `hq up` reports clones still tracking a missing `origin/main` with the fix — test first: `tests/test_modules_and_updates.py::GhPrereqTest` — proof: `python3 -m unittest tests.test_modules_and_updates`
- [ ] 3.6 Global rules and README: branch hierarchy, roles, the agent never approves or merges — test first: `tests/test_engine_is_generic.py` — proof: `python3 -m unittest discover -s tests`

## 4. Workspace and LangBrain (hq-workspace, LangBrain repos)

- [ ] 4.1 Registry: every personal repo `default_branch = "develop"`, standard `git_flow`, `tracker = "github"`, `gate`; LangBrain `auto_pr_target = "develop"`; ADR-016 — test first: `ai-hq tests/test_modules_and_updates.py::RegistryPlaceholdersTest` — proof: `python3 ../ai-hq/scripts/registry.py validate`
- [ ] 4.2 LangBrain: kit 0.2 (`init` upgrade, `roles.yaml`, workflow with gate), verify autopilot and factory follow `auto_pr_target` — test first: `tests/test_ai_skills_library.py` plus a new autopilot target test — proof: `.venv/bin/python -m pytest -q` in LangBrain

## 5. GitHub, real (human gate for every repo)

- [ ] 5.1 `repo_setup.py ai-specs` dry run reviewed by the owner, then `--apply`; inspect branches, protections, labels on GitHub — test first: n/a — proof: `gh api repos/OriolRamos/ai-specs/branches/develop/protection` shows the required checks (human gate)
- [ ] 5.2 Same for ai-skills, ai-hq, hq-workspace, LangBrain; update local clones with the printed commands — test first: n/a — proof: `./hq.sh up --dry-run` reports every repo on `develop` with an upstream (human gate)

## 6. First real change end to end (LangBrain)

- [ ] 6.1 Pick one S change from LangBrain's open work; `/hq-spec` → issue `state:proposed` with block — test first: n/a — proof: issue URL with labels and block
- [ ] 6.2 Owner approves in their terminal; `check-approval` green — test first: n/a — proof: approval comment URL and `ai-specs check-approval` exit 0 (human gate)
- [ ] 6.3 `/hq-factory` builds it; PR into `develop` with `Closes #n`; red `approval` check shown before approval and green after; merged by the owner — test first: the change's own failing test — proof: PR URL with green checks (human gate)
- [ ] 6.4 `/hq-ship release`, `promote`, `tag`: `v` tag on `production` and GitHub release listing the issue — test first: n/a — proof: release URL (human gate)

## 7. Close

- [ ] 7.1 Archive this change in the ai-specs PR; ADRs updated (ai-specs ADR-0002, workspace ADR-016); `/hq-retro` notes — test first: n/a — proof: `openspec validate --all --strict` and `bash scripts/e2e.sh` green on the PR
