## 1. Baseline
- [x] 1.1 Run the gate on `develop` and record it; record the current ASP-035 text and the AI-HQ test `test_unregistered_keeps_base` that pins `develop` as allowed — test first: n/a — proof: `python3 -m unittest discover -s tests && bash scripts/e2e.sh`

## 2. Standard
- [x] 2.1 `docs/standard.md` section 8 (Agents): one sentence on the guard's base list for unregistered repos (`main`, `master`, `develop`, `pre-production`, `production`, plus the local `origin/HEAD` target) and the registry exception (ASP-035) — test first: n/a — proof: `python3 scripts/ai_specs.py lint .`
- [x] 2.2 `docs/adr/README.md`: log entry for the modified ASP-035 (no `VERSION` bump: no format change) — test first: n/a — proof: `python3 -m unittest discover -s tests`

## 3. Consumer and close
- [x] 3.1 Link this change from the AI-HQ change `guard-github-bypasses` (task 2.3 there implements it); its proof is the AI-HQ test named in the scenario — test first: `tests/test_guard_registry.py::UnregisteredDefaultsTest` in ai-hq — proof: `python3 -m unittest tests.test_guard_registry` in ai-hq
- [x] 3.2 `openspec archive guard-base-develop --yes` on this branch before the PR into `develop` — test first: n/a — proof: `npx -y @fission-ai/openspec@1.13.1 validate --all --strict && python3 scripts/ai_specs.py lint .`
