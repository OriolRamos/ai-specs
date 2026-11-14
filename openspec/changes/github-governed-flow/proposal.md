**Size:** L

## Why

The personal flow specifies changes well. A proof per scenario, scaled ceremony, and agent-sized tasks make it better
than the governed company flow at delivering a change. It is weaker at governing one:

- **Private state.** Status, approvals and history live in `hq-workspace/jobs/*/status.json`. Nobody else can see
  them, and an approval is a commit SHA that nothing checks except the orchestrator itself.
- **No traceability chain.** Nothing links issue → spec → commit → PR → release.
- **Multi-repo work is coordinated by one person's job folder.** There is no epic with deliveries.
- **Contracts, impact and gates are paper.** Contracts are described but never validated. Impact is a manual `grep`.
  Each repo's gate is whatever it happens to have.
- **Branches differ per repo.** Personal repos use only `main`, while the product repos use
  `develop → pre-production → production`.
- **Memory is spread over three places** with no rule saying which one is canonical.
- **The flow is unproven.** No change has gone through it end to end.

The goal is to make GitHub the visible, checkable source of truth for every change. That brings memory, traceability
and stability for more people while keeping the strengths of the flow.

## What Changes

- **Tracker (GitHub Issues).**
  - One issue per change (`type:change`) and one per epic (`type:epic`), with each delivery as a sub-issue.
  - One state label at a time: `state:proposed` → `state:approved` → `state:in-progress` → `state:in-review`, then
    closed, plus `state:blocked`.
  - A managed block in the issue body holds the change id, branch, size, spec commit and digest.
- **Traceability.**
  - Branch `change/<issue>-<slug>` from `develop`. Commits carry a `Refs #<issue>` trailer.
  - PR to `develop` with `Closes #<issue>`.
  - The release PR and the GitHub release list the closed issues.
- **Approval with frozen scope and roles.**
  - `openspec/roles.yaml` names the approvers, reviewers and releasers.
  - `ai-specs digest` fingerprints the change folder. Tasks' checkbox state is ignored, so ticking tasks does not
    change it.
  - `ai-specs approve` is run by a human approver and records the digest on the issue. It refuses inside an agent
    session.
  - `ai-specs check-approval` blocks work and merges when the approved digest no longer matches.
- **Branch hierarchy everywhere:** `develop` (default, where work lands), `pre-production`, `production`, with
  annotated tags `vX.Y.Z` on production and hotfixes from production. `main` is renamed to `production` in the
  personal repos.
- **Contracts.**
  - `contracts/<name>/v<N>/` holds a JSON Schema or OpenAPI document, valid and invalid examples, and a README.
  - `ai-specs contract new|check`: conformance through pinned validators, in CI.
- **Product catalog and impact.**
  - A `<product>-platform` repo per multi-repo product holds the epics, the catalog (modules, capabilities,
    interfaces, data) and the shared contracts.
  - `ai-specs impact` lists what a change touches.
- **Quality gate.**
  - Each repo declares one gate command.
  - A kit workflow runs spec validation, the ai-specs lint, contract conformance and the approval check.
  - `develop`, `pre-production` and `production` require those checks and a PR.
- **Unified memory rule:**
  - living specs for behaviour;
  - `docs/adr/` for repo decisions;
  - the platform repo for cross-repo decisions;
  - the workspace for private notes and lessons only;
  - `.agents/memory/` for regenerable context only.
- **AI-HQ fully on this flow.**
  - A `tracker` adapter over `gh`.
  - `/hq-spec` opens the issue and proposes. `/hq-approve` guides the human approval.
  - `/hq-factory` refuses to start without a matching approval and opens the PR to `develop`.
  - `/hq-ship` releases to `pre-production` and promotes to `production` with tags.
  - `/hq-status` and `/hq-triage` read the issues.
  - A `repo_setup` command applies labels, branches, protections, roles and workflows to a repo, with a dry run
    first.
- **Proof:** the first real change runs through the whole flow on LangBrain, from issue to production release.
- **Excludes:**
  - GitHub Projects boards;
  - auto-merge;
  - migrating old backlog items or jobs;
  - changing company repos;
  - Windows support.

## Not to add

- No agent ever approves a spec, merges a PR to a protected branch or pushes to `develop`, `pre-production` or
  `production`.
- No copy of any company tool, script, template or text: the patterns are rebuilt on OpenSpec (MIT) and GitHub.
- No second tracker (Azure, Jira) and no Projects v2 automation in this change.
- No new runtime dependency in ai-specs beyond the Python standard library. Validators run pinned through `npx`,
  like OpenSpec.
- No migration of `BACKLOG.md` items or existing jobs. They finish on the old flow.

## Prior art and reuse

- **OpenSpec 1.13.1.** Changes, specs, validation, archive and config rules: reused as is.
- **ai-specs 0.1.** Standard, `init`, `scaffold`, `lint`, `doctor`: extended to 0.2.
- **ai-hq.** `hq-ship` already implements `release` and `promote` for repos with `develop → pre-production →
  production`: generalised. The OpenSpec mode (`docs/openspec-mode.md`) is extended, `registry.py` gains the
  `tracker` and `gate` fields, and `prereqs.py` gains `gh`.
- **GitHub.** Issues, sub-issues, labels, branch protection with required checks, CODEOWNERS, releases and
  `GITHUB_TOKEN` in Actions: used through the `gh` CLI. There is no own HTTP client.
- **Validators:**
  - `ajv-cli` for JSON Schema conformance, the approach the company flow also takes;
  - `@redocly/cli` for OpenAPI lint.

  Both run pinned through `npx`. No validator is written by hand.
