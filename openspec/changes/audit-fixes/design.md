## Context

The audit ran the real tools end to end, against a simulated GitHub and a real git remote. Six defects and four minor
ones remain, each reproduced or confirmed by reading the code. This change fixes exactly those. It touches ai-specs
(kit 0.2.1), ai-hq, hq-workspace and LangBrain.

## Decisions

### D1 · Purpose travels in the delta
OpenSpec reads a delta's `## Purpose` only when the capability is created, and strict validation requires at least 50
characters.

- Every delta spec starts with `## Purpose`. Lint enforces it only when `openspec/specs/<capability>/spec.md` does not
  exist yet, so changes to existing capabilities are unaffected.
- The kit rules ask for it always, because that is harmless.

*Rejected:* editing the living spec after archive. That is a manual step, and the standard forbids editing living
specs by hand.

### D2 · PR to issue
`issue_of_pr` takes `Closes #n` when there is exactly one, else the number in a head branch `change/<n>-<slug>` or
`hotfix/<n>-<slug>`, else it fails. Back-merges keep `Refs #n`, so merging into `develop` does not close the issue
early. `ship hotfix` closes it when both back-merges are in.

### D3 · Dependency bots
The approval job condition adds
`github.event.pull_request.user.login != 'dependabot[bot]' && github.event.pull_request.user.login != 'renovate[bot]'`.
A required job skipped by its `if` reports success, so bot PRs still need `ai-specs` and `gate`. People cannot use
this: the PR author is set by GitHub.

### D4 · Builders check approval
- **LangBrain helper `context/approval_gate.py`** (stdlib):
  - `runs_ai_specs(path)` tells whether the repo runs ai-specs (its config starts with `# ai-specs:kit`);
  - `kit_cli(hq_root)` finds the kit: `AI_SPECS_HOME`, else the `ai-specs` sibling of ai-hq;
  - `check(path, issue)` runs `ai_specs.py check-approval`, and only exit 0 is approved.
- **Autopilot filter:** for an issue of a GitHub-tracked repo that runs ai-specs, an issue that is not approved is
  skipped and reported as "needs an approved spec".
- **Factory preflight:** for every ai-specs repo of the job, `status.openspec.issues[<repo>]` must exist and pass,
  else a `ValueError` stops the job before any worktree work.
- **ai-hq:** `tracker.py propose … --job <id>` writes `openspec.issues[<repo>] = n` into the job's `status.json`.

### D5 · Order
Approval covers tasks, because their wording is part of the digest. The order is therefore spec → tasks → approve →
build. `/hq-spec` ends by proposing `/hq-tickets`; `/hq-tickets` ends by proposing `/hq-approve`.

### D6 · Data repos stay off the approval flow
A repo that only stores private state (the AI-HQ workspace) has `tracker = "none"`, one `main` branch, no protected
branch in the registry (so the local guard allows its commits) and a format gate. The standard says so in section 7.

### D7 · Minor fixes
- `ship.release` and `ship.promote` run `git fetch --tags origin` first.
- The ai-hq `ci.yml` runs on pushes to `develop`, `pre-production` and `production`.
- `repo_setup.CHECKS["production"]` adds `approval`. It runs for `hotfix/*` heads and is skipped (success) for
  promotions.
- `docs/adr/README.md` in ai-specs indexes the method decisions, including workspace ADR-013 to ADR-016 by
  reference.

## Compatibility and migration

- **Kit 0.2.1.**
  - Repos on 0.2.0 keep working.
  - The Purpose rule only fails changes that would already fail OpenSpec at archive.
  - The workflow change (bot skip) reaches a repo when `init` is re-run. Its workflow then pins `v0.2.1`, so that tag
    must exist first.
  - Release order: merge ai-specs, tag `v0.2.1`, then merge the repos.
- **`github-governed-flow`** gets `## Purpose` in its seven deltas. Its digest changes and the new digest is recorded
  in the workspace job, the same bootstrap approval as before.
- **hq-workspace** has no GitHub settings yet (repo_setup has not run), so moving it back to `main` only changes the
  registry.

## Security and operations

- The bot exemption is keyed on the PR author, which a person cannot set, and covers only the approval job.
- The builders' gate runs the same `check-approval` as CI, so exit 2 (no `gh`, no network) never counts as approved.

## Test strategy

- **ai-specs:** lint Purpose tests (new and existing capability), `issue_of_pr` by branch, workflow condition test,
  and the e2e extended with `validate --all --strict` after archive and a hotfix-branch approval check.
- **ai-hq:**
  - `test_flow_rehearsal` covers the whole flow, with a fake gh shared by both tools; it is skipped without an
    `openspec` CLI;
  - `ship` fetches tags;
  - `repo_setup` production checks;
  - `tracker propose --job` writes the issue;
  - the skill order.
- **LangBrain:** pytest for `approval_gate` (stdlib, with a fake kit), the autopilot filter that skips unapproved
  issues, and the factory preflight error. They run in its CI.
- **Behavioural check:** the rehearsal itself.

## Change impact

| Changed | Used by today | Breaks? | Mitigation / rollback |
|---|---|---|---|
| lint Purpose rule | changes creating capabilities (github-governed-flow, future ones) | github-governed-flow lint until its deltas get Purpose (done here) | revert the rule |
| `issue_of_pr` fallback | CI approval job, `/hq-factory` | no (more PRs resolve, none fewer) | revert |
| workflow bot skip | adopting repos after `init` | no | re-run `init` with 0.2.0 |
| LangBrain autopilot and factory gate | autopilot runs on ai-specs repos | unapproved issues are no longer built (intended) | revert; or approve the issue |
| hq-workspace registry → `main`, tracker none | `hq up` updates, guards | no (fewer guards on a data repo) | registry revert |
| `repo_setup` production checks | future setups | no | revert |

## Rollback

Revert the merge commits in each repo, pin kit `v0.2.0`, and re-run `init`. Nothing on GitHub changes in this change.
