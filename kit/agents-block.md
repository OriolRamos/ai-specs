<!-- ai-specs:begin (managed by `ai_specs.py init`; change the ai-specs kit, not this block) -->
## Specs and changes (ai-specs)

This repo follows the ai-specs standard on top of OpenSpec:

- What the system does today lives in `openspec/specs/`. Every change lives in `openspec/changes/<id>/`
  (proposal, delta specs, design, tasks) and is archived with `openspec archive <id> --yes` in the same PR once
  its tasks pass.
- Requirement ids are `{{PREFIX}}-NNN`; every scenario ends with a `- **Proof:**` line; every task carries
  `test first` and `proof`.
- `**Size:** S|M|L` in the proposal decides the ceremony: S = proposal + tasks (+ delta specs when behaviour
  changes); M adds prior art and change impact; L adds `design.md`.
- Before calling a change ready: `openspec validate <id> --strict` and, when ai-specs is available,
  `python <ai-specs>/scripts/ai_specs.py lint . <id>`.
- Status, owners, approvals and logs are not kept in this repo.
<!-- ai-specs:end -->
