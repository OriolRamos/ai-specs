## 0. Approval

- [x] 0.1 [owner] Approve (asked in conversation: "arreglem tot", work lands on develop in the owner's repos) — test first: n/a — proof: recorded approval (human gate)

## 1. ai-specs

- [x] 1.1 `ai-specs leak-check` (tracked files or a range), included in `lint` when the terms file exists; audit-fixes ASP-014 updated to the develop working branch — test first: `tests/test_leakcheck.py` — proof: `python3 -m unittest discover -s tests`

## 2. ai-hq

- [x] 2.1 Guard: registry `protected` list for registered repos, base list otherwise; leak check on `git push` — test first: `tests/test_guard_registry.py` — proof: `python3 -m unittest discover -s tests`

## 3. hq-workspace

- [x] 3.1 Registry: workspace `default_branch = "develop"`, `git_flow = ["develop", "main"]`, `protected = ["main"]`; ADR-018; `develop` created from `main` — test first: `ai-hq tests/test_registry_gate.py::WorkspaceTest` — proof: `python3 ../ai-hq/scripts/registry.py validate`
