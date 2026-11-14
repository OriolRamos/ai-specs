## 0. Approval and pilot setup

- [ ] 0.1 [owner] Approve this change (answers: Ollama from day one; the company brain is local-only and never uploaded) — test first: n/a — proof: the recorded approval with the answers (human gate)
- [ ] 0.2 [owner] Per machine: install RSC Brain locally with its launcher (SHA-256 checked, localhost only), keep the installation key, create the machine's brains (work: `work`; personal: `personal`, `langbrain`), enable `pgvector`, `pg_search` and Ollama meaning search — test first: n/a — proof: the web's Overview lists the brains and search reports `bm25` and the Ollama provider (human gate)

## 1. ai-specs (standard)

- [x] 1.1 Memory section: taxonomy table with the brain row, the "links, does not define" rule and one-memory-per-machine — test first: `tests/test_ai_specs.py::StandardMemoryTest` — proof: `python3 -m unittest tests.test_ai_specs.StandardMemoryTest`

## 1b. ai-brain (new repo: manager per machine)

- [ ] 1b.1 Repo skeleton, CLI `ai-brain` (init, up, down, status, upgrade) with ParadeDB + Ollama compose, pinned RSC Brain release and SHA-256 check, `machine.toml` outside repos — test first: `tests/test_ai_brain.py::InstallTest`, `ConfigTest` — proof: `python3 -m unittest discover -s tests`
- [ ] 1b.2 Sharing policies: `backup` (ciphertext only) and `publish` (approved wiki markdown only), refusals naming the lock, guard rule for the copy folders — test first: `tests/test_ai_brain.py::PolicyTest` — proof: `python3 -m unittest discover -s tests`
- [ ] 1b.3 `activate`/`deactivate` (MCP, hooks, overdue check, weekly job) used by the AI-HQ module — test first: `tests/test_ai_brain.py::ActivateTest` — proof: `python3 -m unittest discover -s tests`

## 2. ai-skills (neutral skills, usable on the work machine)

- [ ] 2.1 `brain-map` skill and `scripts/brain_map_scope.py` (which repos, which paths since the mapped commit) — test first: `tests/test_brain_tools.py::MapScopeTest` — proof: `python3 -m unittest tests.test_brain_tools && python3 scripts/lint.py`
- [ ] 2.2 `brain-consolidate` skill and `scripts/brain_decay.py` (decay score and forgetting rule) — test first: `tests/test_brain_tools.py::DecayTest` — proof: `python3 -m unittest tests.test_brain_tools && python3 scripts/lint.py`

## 3. ai-hq (module, registry, skills)

- [ ] 3.1 Module `brain`: MCP registration, the two RSC Brain hooks, the overdue check hook and the weekly job (systemd user timer or cron) with the restricted allowlist; contributor-only token; removed when not chosen — test first: `tests/test_brain_module.py::InstallTest` (ai-hq); `tests/test_ai_brain.py::TokenScopeTest`, `ScheduleTest`, `OverdueTest` (ai-brain, where that code lives) — proof: `python3 -m unittest tests.test_brain_module` in ai-hq and `python3 -m unittest discover -s tests` in ai-brain
- [ ] 3.2 Registry `[hq] brain_url`, stack `brain` (RSC Brain + Ollama), `[projects.*] brain`; prereqs Docker for `brain` — test first: `tests/test_brain_module.py::RegistryTest` — proof: `python3 -m unittest tests.test_brain_module && python3 scripts/registry.py validate`
- [ ] 3.3 Skill hooks in grill, spec, tickets, factory, triage, retro (no-op without a brain; gap rule calls `brain-map`) — test first: `tests/test_brain_module.py::SkillHooksTest` — proof: `python3 -m unittest tests.test_brain_module && python3 scripts/lint_skills.py`

## 4. hq-workspace

- [ ] 4.1 Registry values (`brain_url`, `brain` per repo), ADR-019 (ADR-018 is taken), pilot job with the personal machine's `PILOT.md` (the work machine's record stays local, D8) — test first: n/a — proof: `python3 ../ai-hq/scripts/registry.py validate`

## 5. Pilot (two weeks per machine)

- [ ] 5.1 Work machine: `brain-map` over `~/develop`, daily use, one consolidation — test first: n/a — proof: links in the local record `~/.local/share/rsc-brain/pilot.md`, never in the workspace (human gate)
- [ ] 5.2 Personal machine: `brain-map` over `~/personal-assistant`, one real LangBrain change from `/hq-grill` to merge with the brain supplying prior art, a later session recovering saved attempts — test first: n/a — proof: links in `PILOT.md` (human gate)
- [ ] 5.3 Measure and decide per machine (adopt or retire with markdown export) — test first: n/a — proof: the four measures and the decision in each pilot record (human gate)
