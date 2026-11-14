**Size:** L

## Why

An audit of the GitHub-governed flow combined two things: an end-to-end rehearsal (issue → spec → approval → build →
archive → PR → release → promote → tag), using the real ai-hq and ai-specs tools against a simulated GitHub and a real
git remote, and a design review. The core flow works. Six defects would still block or bypass it in concrete cases:

1. **New capabilities break CI.** Archiving a change that creates a capability writes a placeholder `Purpose`.
   `openspec validate --all --strict` rejects it, and it also rejects a Purpose shorter than 50 characters. The
   rehearsal reproduced this.
2. **Hotfix back-merges cannot merge.** The back-merge PR into `develop` says `Refs #n`, not `Closes #n`, and
   `check-approval --pr` requires exactly one closed issue.
3. **The private data repo is on the approval flow.** hq-workspace has a protected `develop`, so every log line,
   lesson or backlog edit would need an issue, an approval and a PR.
4. **Dependency bots.** With protections, Dependabot PRs can never merge, because they have no spec. Without them,
   LangBrain's `automerge` merges them anyway.
5. **Ambiguous order.** `/hq-spec` proposes `/hq-approve` and `/hq-tickets` in either order. Tasks written after the
   approval make it stale and stop the factory.
6. **Builders bypass the gate.** LangBrain's autopilot and factory recipes can build without checking the approval.

There are also minor defects:
- `ship release`/`promote` compute "since the last tag" without fetching tags.
- The `ci.yml` of ai-hq runs on pushes to `main`, which disappears.
- Hotfix PRs into `production` do not require the approval check.
- The method ADRs live only in the private workspace.

## What Changes

- **Purpose of new capabilities.**
  - Every delta spec carries a `## Purpose` of at least 50 characters. OpenSpec uses it when the capability is new and
    ignores it otherwise.
  - `ai-specs lint` requires it whenever the living spec does not exist yet.
  - The scaffold template and kit rules include it, and the e2e validates `--all --strict` after archive.
  - The deltas of the active change `github-governed-flow` get their Purpose, which changes its digest; it is
    recorded again.
- **PR to issue.** `check-approval --pr` reads the issue from `Closes #n` or, when there is none, from the head branch
  `change/<n>-…` or `hotfix/<n>-…`.
- **Dependency bots.** The kit workflow skips the `approval` job for PRs authored by `dependabot[bot]` and
  `renovate[bot]`. A skipped required job reports success; the `ai-specs` and `gate` checks still apply.
- **Builders check approval:**
  - LangBrain's autopilot only builds issues whose change passes `check-approval` in repos that run ai-specs;
  - LangBrain's factory refuses to start such a repo's job without the job's approved issue;
  - ai-hq's `tracker propose --job` records the issue on the job.
- **Order.** `/hq-spec` → `/hq-tickets` → `/hq-approve` → `/hq-factory`, in the skills and in the flow guide.
- **Data repos.** hq-workspace runs on a single `main` with `tracker = "none"`, no protected branch and a format gate.
  The standard says private state repos stay off the approval flow.
- **Minor fixes:**
  - `ship` fetches tags first;
  - the ai-hq `ci.yml` runs on the three branches;
  - `repo_setup` requires `approval` on `production`;
  - an ADR index in ai-specs lists the method decisions.
- **Rehearsal as a test.** The end-to-end rehearsal becomes an ai-hq integration test. It runs when an `openspec` CLI
  is available.
- **Kit 0.2.1.** Adopting repos pick it up with `init`.
- **Excludes:**
  - new features;
  - changes to company repos;
  - turning the autopilot off;
  - GitHub Projects.

## Not to add

- No exemption from the approval for people. Only the named dependency bots skip it, and only the approval job.
- No change to the digest algorithm or to who may approve.
- No migration of workspace ADRs into repos. The index points to them.

## Prior art and reuse

- **OpenSpec 1.13.1.** Its own rule: "a `## Purpose` in a delta is read only when the capability is created". Reused
  instead of editing living specs by hand.
- **Existing code reused:**
  - `approval.issue_of_pr`, `ghcli.pull` (the PR's `head.ref`);
  - `tracker.GitHubTracker`, `ship.py`, `repo_setup.CHECKS`;
  - LangBrain's autopilot filter and factory preflight.
- **GitHub Actions.** A job skipped by its `if` reports success for required checks, so no extra workflow is needed.
- **The rehearsal script** from the audit becomes the integration test.
