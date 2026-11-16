**Size:** M

## Why
Section 8 of the standard says agents never merge into `develop`, `pre-production` or `production`, and never push to
them. ASP-035 gives repos that are not in the registry a base list of protected branches: `main`, `master`,
`pre-production`, `production`. `develop` is not in it.

On a work machine, every company checkout is unregistered, by design: the registry is personal. An end-to-end test
fed the real guard push commands from such a checkout. `git push origin develop`, `git push origin HEAD:develop` and a
bare `git push` on `develop` all got no decision, so an agent could push straight to the branch the standard reserves
for reviewed PRs. The same holds for a repo whose integration branch has another name: its default branch, as
`origin/HEAD` names it locally, is not protected either.

The registry exists so a person can loosen protection for their own repo (the private workspace works on `develop`).
In a repo nobody registered, the base list should match the standard's own rule.

## What Changes
- **ASP-035 modified.** Registered repos are unchanged: exactly the registry's `protected` list. For any other repo,
  the base list becomes:
  - `main`, `master`, `develop`, `pre-production` and `production`;
  - plus the branch `refs/remotes/origin/HEAD` points to, when that ref resolves in the local clone.

  The guard reads only local git metadata: no fetch, no network.
- **Docs:** `docs/standard.md` section 8 (Agents) names the guard's base list and the registry exception in one
  sentence; ADR log note in `docs/adr/README.md`. No kit format change, so there is no `VERSION` bump.
- **Consumer:** AI-HQ's guard implements it in its own change (ai-hq `guard-github-bypasses`, HQ-123), approved
  separately.
- **Excludes:**
  - the guard's code (lives in AI-HQ);
  - server-side branch protection or rulesets;
  - any change to how the registry is read;
  - other forges.

## Not to add
- No new registry key or opt-out flag: a repo that needs `develop` writable is registered with its own `protected`
  list.
- No network lookup of the remote's default branch.
- No change to lint, the kit's `config.yaml.tmpl` or the card workflow.

## Prior art and reuse
| Need | Found | Decision |
|---|---|---|
| Protected-branch rule for unregistered repos | ASP-035 (change `local-guards`) | **Extend** the base list; keep the registry rule |
| Agent push rule | standard section 8, "Agents … never push to them" | **Reuse** as the source of the list |
| Default branch without network | `git symbolic-ref refs/remotes/origin/HEAD` (set by `git clone` and `git remote set-head`) | **Reuse**; nothing added when unset |

## Change impact
| Changed thing | Used by today | Breaks? | Mitigation / rollback |
|---|---|---|---|
| ASP-035 base list gains `develop` and the local `origin/HEAD` target | AI-HQ guard (`hooks/guard_bash.py`, `protected_for`) and its test `test_unregistered_keeps_base` | Agents can no longer push `develop` or the default branch of an unregistered repo. Its test flips for `develop` | register the repo with its own `protected` list; revert this change |
| `docs/standard.md` section 8 sentence | readers of the standard, repos that adopted the kit (managed CLAUDE block unchanged) | No | revert |
