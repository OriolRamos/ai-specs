<!-- ai-specs:begin (managed by `ai_specs.py init`; change the ai-specs kit, not this block) -->
## Specs, approval and branches (ai-specs {{VERSION}})

This repo follows the ai-specs standard on top of OpenSpec and GitHub:

- **Where things are.** What the system does today is in `openspec/specs/`. Every change lives in
  `openspec/changes/<id>/` and has one GitHub issue (`type:change`, one `state:*` label). Status, owners and
  approvals live on the issue, never in these files.
- **Approval before work.** No code is written for a change until `ai-specs check-approval . <issue>` passes. Only a
  person listed in `openspec/roles.yaml` approves, in their own terminal (`ai-specs approve`). Agents never approve,
  never merge and never push to `develop`, `pre-production` or `production`.
- **Branches.** Work branches are `change/<issue>-<slug>` from `develop`, and commits carry `Refs #<issue>`. The PR
  goes into `develop` with `Closes #<issue>`. Releases go `develop → pre-production → production`, with tags
  `vX.Y.Z`. Hotfixes branch from `production` and are merged back.
- **Spec format.** Requirement ids are `{{PREFIX}}-NNN`, every scenario ends with `- **Proof:**`, and every task
  carries `test first` and `proof`. `**Size:** S|M|L` decides which artifacts are required.
- **Before calling a change ready:** `openspec validate <id> --strict`, `ai-specs lint . <id>`,
  `ai-specs contract check .` and the repo's gate. Archive with `openspec archive <id> --yes` in the same PR.
- **Decisions** go to `docs/adr/` (`ai-specs adr new . "<title>"`).
<!-- ai-specs:end -->
