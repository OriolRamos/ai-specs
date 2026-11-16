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
- Code, comments, commits and docs in English. Conventional Commits. Branch `change/<slug>` (or `feat/<slug>`) cut from `develop` → PR to `develop` (`develop` is the default branch).

<!-- ai-specs:begin (managed by `ai_specs.py init`; change the ai-specs kit, not this block) -->
## Specs, approval and branches (ai-specs 0.3.0)

This repo follows the ai-specs standard on top of OpenSpec and GitHub:

- **Where things are.** What the system does today is in `openspec/specs/`. Every change lives in
  `openspec/changes/<id>/` and has one GitHub issue (`type:change`, one `state:*` label). Status, owners and
  approvals live on the issue, never in these files.
- **Approval before work.** No code is written for a change until `ai-specs check-approval . <issue>` passes. Only a
  person listed in `openspec/roles.yaml` approves: by ticking the approval card on the issue, or in their own
  terminal (`ai-specs approve`). Agents never tick the card, never post approval markers, never approve, never merge
  and never push to `develop`, `pre-production` or `production`.
- **Branches.** Work branches are `change/<issue>-<slug>` from `develop`, and commits carry `Refs #<issue>`. The PR
  goes into `develop` with `Closes #<issue>`. Releases go `develop → pre-production → production`, with tags
  `vX.Y.Z`. Hotfixes branch from `production` and are merged back.
- **Spec format.** Requirement ids are `ASP-NNN`, every scenario ends with `- **Proof:**`, and every task
  carries `test first` and `proof`. `**Size:** S|M|L` decides which artifacts are required.
- **Before calling a change ready:** `openspec validate <id> --strict`, `ai-specs lint . <id>`,
  `ai-specs contract check .` and the repo's gate. Archive with `openspec archive <id> --yes` in the same PR.
- **Decisions** go to `docs/adr/` (`ai-specs adr new . "<title>"`).
<!-- ai-specs:end -->
