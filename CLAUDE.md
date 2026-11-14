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
- Before saying done: `python3 -m unittest discover -s tests`. If `kit/` changed, also run the end-to-end check
  with the real CLI in a scratch folder:
  `ai_specs.py init . --prefix XX` → `openspec new change demo` → `ai_specs.py scaffold . demo --size S --capability x`
  → fill → `ai_specs.py lint .` → `openspec validate demo --strict` → `openspec instructions proposal --change demo`
  (no parse warning, rules listed) → `openspec archive demo --yes`.
- Code, comments, commits and docs in English. Conventional Commits. Branch `feat/<slug>` → PR to `main`.
