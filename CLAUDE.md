# ai-specs · Working on this repo

This repo is the ai-specs standard and kit (see `README.md` and `docs/standard.md`). When editing it:

- The standard is generic: no person, product or company names, and no company process tooling. It builds on
  OpenSpec (MIT) and on public patterns only.
- Every rule in `docs/standard.md` that can be checked mechanically is checked by `scripts/ai_specs.py lint`, and
  the OpenSpec rules in `kit/config.yaml.tmpl` say the same thing. Change all three together.
- Never break repos that already adopted the kit: lint checks active changes only; a new required section or
  format needs a `VERSION` bump and a note in the ADR log; ids and archived files are never rewritten.
- `kit/config.yaml.tmpl` rule items are single-quoted YAML scalars with no `'` inside (OpenSpec ignores a config it
  cannot parse; a test guards it).
- Before saying done: `python3 -m unittest discover -s tests` and, if `kit/` or `scripts/` changed,
  `bash scripts/e2e.sh` (real OpenSpec CLI in a scratch folder; CI runs both).
- Code, comments, commits and docs in English. Conventional Commits. Branch `feat/<slug>` → PR to `main`.

<!-- ai-specs:begin (managed by `ai_specs.py init`; change the ai-specs kit, not this block) -->
## Specs and changes (ai-specs)

This repo follows the ai-specs standard on top of OpenSpec:

- What the system does today lives in `openspec/specs/`. Every change lives in `openspec/changes/<id>/`
  (proposal, delta specs, design, tasks) and is archived with `openspec archive <id> --yes` in the same PR once
  its tasks pass.
- Requirement ids are `ASP-NNN`; every scenario ends with a `- **Proof:**` line; every task carries
  `test first` and `proof`.
- `**Size:** S|M|L` in the proposal decides the ceremony: S = proposal + tasks (+ delta specs when behaviour
  changes); M adds prior art and change impact; L adds `design.md`.
- Before calling a change ready: `openspec validate <id> --strict` and, when ai-specs is available,
  `python <ai-specs>/scripts/ai_specs.py lint . <id>`.
- Status, owners, approvals and logs are not kept in this repo.
<!-- ai-specs:end -->
