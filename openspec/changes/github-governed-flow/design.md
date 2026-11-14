## Context

There are five personal repos: ai-specs, ai-skills, ai-hq, hq-workspace and LangBrain. Only LangBrain runs ai-specs
0.1, and it has no specs yet. ai-hq orchestrates the work. The job state lives in the private hq-workspace. The
product repos (Clothy) already use `develop → pre-production → production`. Today `gh` is not installed on the
machine, and branches, labels and protections are configured by hand, if at all.

## Decisions

### D1 · GitHub is the source of truth for state; OpenSpec for intent

- **Issues** carry the state, the owner and the approval.
- **OpenSpec changes** carry the intent, requirements, design and tasks.
- **`status.json`** in the workspace becomes a local cache of the issue, rebuilt from it at any time.

*Rejected:* keeping the state in the workspace (invisible to others); GitHub Projects v2 (an extra API surface for no
benefit at this size).

### D2 · Issue model

| Issue | Where | Labels | Body |
|---|---|---|---|
| Change | the repo that changes | `type:change`, one `state:*`, `size:S/M/L` | free text + managed block |
| Epic | `<product>-platform` repo; or the repo itself for a single-repo product | `type:epic`, one `state:*` | free text + list of deliveries; deliveries are **sub-issues** |

The managed block in a change issue is rewritten only by the tools:

```
<!-- ai-specs:change -->
change: <change-id>
branch: change/<issue>-<slug>
size: M
spec_commit: <sha of the last commit touching the change folder>
digest: sha256:<hex>
<!-- /ai-specs:change -->
```

### D3 · States

`state:proposed → state:approved → state:in-progress → state:in-review → closed (done)`, plus
`state:blocked` (with a comment saying why). Exactly one `state:*` label at a time; the tools swap them.

- A scope change (the digest differs from the approved one) moves the issue back to `state:proposed`.
- Closing happens through the PR's `Closes #n` on merge into `develop`.
- An epic is closed by `/hq-ship` when all its sub-issues are closed.

### D4 · Digest

The digest is a `sha256` over the change folder `openspec/changes/<id>/`, computed as follows:
- **Files:** every regular file, sorted by POSIX path relative to the folder.
- **Per file:** the path, a NUL byte, then the content with CRLF normalised to LF.
- **In `tasks.md`:** every checkbox `- [x]` / `- [X]` is normalised to `- [ ]` before hashing.

So ticking tasks never invalidates an approval, but any edit to the proposal, the specs, the design or the wording of a
task does. After archive the folder moves. The approval check then reads the archived copy
(`openspec/changes/archive/*-<id>/`), so a PR carrying code plus archive still verifies.

### D5 · Roles and approval

`openspec/roles.yaml` (simple `key: [list]` YAML, parsed by a stdlib reader that accepts only this shape):

```yaml
approvers: [OriolRamos]     # may approve specs (min_approvals distinct approvers)
reviewers: [OriolRamos]     # code review on PRs (CODEOWNERS is generated from it)
releasers: [OriolRamos]     # may merge release and promotion PRs
min_approvals: 1
```

- **`ai-specs approve <issue>`.** Run by a human. It:
  1. resolves the logged-in `gh` user and refuses if that user is not an approver;
  2. refuses when it runs inside an agent session (`CLAUDECODE` set) or without a terminal;
  3. shows the digest and asks the human to type its first 8 characters;
  4. posts the comment `<!-- ai-specs:approval digest=sha256:… commit=<sha> by=<login> -->` plus a readable line;
  5. sets `state:approved`.
- **`ai-specs check-approval <issue>`** passes when two things hold:
  - at least `min_approvals` distinct approvers have an approval comment whose digest equals the current digest of the
    change (live or archived);
  - each of those comments was written by that approver: the comment author must match the `by=` field, which GitHub
    guarantees.

  It exits with `0` = approved, `1` = not approved or stale, `2` = cannot check.

*Rejected:* approval by label only (anyone with triage rights can add a label, and the label carries no digest);
approval by PR review of a spec-only PR (adds a PR per change and a second merge into `develop`).

### D6 · Branches and protections

Every adopting repo has three long-lived branches and no direct pushes:

- **`develop`**: the default branch.
  - Work branches come from it: `change/<issue>-<slug>`.
  - PRs need the `ai-specs` and `gate` checks, the approval check, and 1 review by a reviewer. The owner may bypass the
    review while alone. That is GitHub's "allow specified actors to bypass", and it is recorded.
- **`pre-production`**: only release PRs from `develop`. Checks required.
- **`production`**: only promotion PRs from `pre-production` and hotfix PRs.
  - Each promotion is tagged `vX.Y.Z` (annotated) and gets a GitHub release listing the issues.
  - A hotfix branches from production (`hotfix/<issue>-<slug>`), and after it ships it is merged back into
    `pre-production` and `develop` by PR.

`repo_setup` (ai-hq) applies all of this, idempotently, after showing a dry-run plan. Renaming `main` to `production`
uses GitHub's branch rename, so open PRs and links keep working.

### D7 · Contracts

```
contracts/<name>/v<N>/
  schema.json | openapi.yaml
  examples/valid/*.json      # must validate
  examples/invalid/*.json    # must fail
  README.md                  # owner (provider), consumers, compatibility notes
```

- **Validators.** `ai-specs contract check [<repo>]` runs them pinned through `npx`:
  - JSON Schema: `ajv-cli@5.0.0` (`ajv validate --spec=draft2020 --strict=false`), on every example; an invalid example
    that validates is an error.
  - OpenAPI: `@redocly/cli@1.34.5 lint`.
- **Breaking changes** create `v<N+1>`. A version folder that is already released is never edited.
- **Consumers** reference `<provider>/<name>/v<N>` in the catalog.

### D8 · Product catalog and impact

The `<product>-platform` repo holds `catalog/product.json`. It is validated by `ai-specs catalog check`, which checks
that every reference resolves, every id is unique, and every contract path exists in the platform repo or in a
registered checkout.

```json
{ "product": "clothy",
  "modules": [{"id": "clothy-backend", "repo": "OriolRamos/Clothy-Backend"}],
  "capabilities": [{"id": "outfits", "owner": "clothy-backend", "modules": ["clothy-backend", "clothy-frontend"],
                    "specs": ["clothy-backend:openspec/specs/outfits/spec.md"]}],
  "interfaces": [{"id": "outfits-api-v1", "contract": "contracts/outfits-api/v1", "provider": "clothy-backend",
                  "consumers": ["clothy-frontend"]}],
  "data": [{"id": "outfits-db", "owner": "clothy-backend", "writers": ["clothy-backend"], "readers": []}] }
```

`ai-specs impact <catalog> <id>` prints every capability, interface, data asset, module and spec that references the
id. M and L proposals paste its output into the Change impact table.

### D9 · Quality gate

- Each repo declares exactly one gate command: `gate` in the AI-HQ registry, and the same command in the repo's README.
- The kit ships `.github/workflows/ai-specs.yml` with three jobs:
  - **`ai-specs`**: `openspec validate --all --strict`, `ai-specs lint`, `ai-specs contract check`;
  - **`approval`**: on PRs, `ai-specs check-approval --pr`, which reads `Closes #n` from the PR body and uses
    `GITHUB_TOKEN` with `issues: read`;
  - **`gate`**: the repo's own gate.
- The standard sets the minimum a gate must contain: format, lint, typecheck where the language has one, and tests.
  Thresholds belong to each repo.

### D10 · Memory

| What | Where | Canonical for |
|---|---|---|
| Behaviour today | `openspec/specs/` of the repo | what the system does and how each behaviour is proved |
| History of changes | `openspec/changes/archive/` + closed issues + releases | why and when it changed |
| Repo decisions | `docs/adr/NNNN-*.md` in the repo | technical decisions of that repo |
| Cross-repo decisions | `docs/adr/` in the `<product>-platform` repo, or the ai-specs repo for the method | product- and method-wide decisions |
| Private notes, lessons, taste | hq-workspace | the owner only; never the only place a decision lives |
| Regenerable context | `.agents/memory/` | onboarding speed; can be rebuilt from the above |

### D11 · AI-HQ integration

- **`scripts/tracker.py`.** A `Tracker` protocol with the `github` backend (`gh issue|pr|api|release`) and a `null`
  backend for repos with `tracker = "none"`. All its calls are in one module, and tests use a fake `gh` on `PATH`.
- **Registry.**
  - `tracker = "github"` (default for repos with a GitHub remote).
  - `gate = "<command>"`.
  - `product = "<id>"`.
  - `default_branch = "develop"` and `git_flow = ["change/*", "develop", "pre-production", "production"]` for every
    repo.
- **Skills:**
  - **`/hq-spec`** creates the issue (`state:proposed`) and the branch, writes and checks the change, pushes, writes
    the managed block, and asks the approvers.
  - **`/hq-approve <repo>#<n>`** (new) shows the approver what to review and the exact command to run in their own
    terminal. It never runs `approve` itself.
  - **`/hq-factory`:**
    - runs `check-approval` before the first task and again before the PR;
    - moves the issue to `state:in-progress`; commits carry `Refs #n`;
    - opens the PR to `develop` with `Closes #n` and moves the issue to `state:in-review`.
  - **`/hq-ship`:**
    - `release` opens the PR develop→pre-production, with a changelog grouped from the PRs and issues closed since the
      last tag;
    - `promote` opens the PR pre-production→production. After the human merge, `tag` creates `vX.Y.Z` and the GitHub
      release.
  - **`/hq-status` and `/hq-triage`** list the open issues of the registered repos by state. `BACKLOG.md` keeps its
    old items read-only.
- **`scripts/repo_setup.py <repo>`** shows a dry-run plan by default and applies with `--apply`. It creates:
  - the labels;
  - `develop` and `pre-production`, the `main → production` rename, and `develop` as the default branch;
  - the branch protection rules;
  - `roles.yaml` and CODEOWNERS;
  - the kit workflow.
- **`prereqs.py`.** `gh` becomes required for module `hq`. `hq up` reports when `gh auth status` fails.

## Compatibility and migration

- **Kit 0.1 → 0.2.** `init` upgrades the config, writes `roles.yaml` if missing, and adds the workflow.
  - The lint rules added in 0.2 (issue reference in the proposal, `roles.yaml` present) apply only to changes created
    with kit 0.2. Changes whose `.openspec.yaml` predates the upgrade keep the 0.1 rules.
  - LangBrain has no active change, so nothing is affected.
- **Branch rename on each repo:**
  1. On GitHub: create `develop` and `pre-production` from `main`, rename `main` to `production`, and make `develop`
     the default.
  2. In each local clone: `git fetch && git branch -m main production && git branch -u origin/production production &&
     git switch develop`. `repo_setup` prints these commands, and `hq up` reports clones still tracking a missing
     `origin/main`.
  3. CI triggers move from `main` to the three branches.
- **Registry.** `auto_pr_target = "main"` (LangBrain) becomes `develop`. LangBrain's `github_autopilot` and
  `hq_factory` read the target from the registry, so they follow it; this is to be verified in its tests.
- **Old jobs** (`jobs/*` without `openspec`) and `BACKLOG.md` items finish on the old flow. Nothing is migrated.

## Security and operations

- **Approval** is bound to a human `gh` identity listed in `roles.yaml` and to a digest of the exact content. It
  refuses inside agent sessions and without a TTY. Comment authorship is verified through the API, so it cannot be
  forged in the body.
- **Agents** cannot push to the three branches because protections apply to everyone. The owner's bypass covers only
  the review count, never the checks.
- **Tokens.**
  - `gh` keeps its own token in the OS keyring.
  - Workflows use `GITHUB_TOKEN` with least privileges (`contents: read`, `issues: read`, `pull-requests: read`).
  - No token is written to any repo or to the workspace.
- **Failure modes.** No `gh`, no auth or no network → the tools exit `2` with the exact fix and never fall back to
  "approved".

## Test strategy

- **ai-specs.**
  - Unit tests: digest stability (checkbox ticks, CRLF, file order), the roles parser, the approval comment parser,
    check-approval with a fake `gh` (missing, stale, wrong author, enough approvals), contract check with fake
    validators, catalog check and impact, and the lint 0.1/0.2 rules.
  - `scripts/e2e.sh` is extended with digest, approve (simulated TTY, fake `gh`) and archive-then-check.
- **ai-hq.** Tracker tests with a fake `gh` that records calls; `repo_setup` plan tests (dry run lists exact calls,
  apply is idempotent); skill routing tests; registry fields.
- **Real GitHub,** with explicit OK:
  1. `repo_setup` on ai-specs first and inspect the result;
  2. then the other repos;
  3. then one real S change on LangBrain from issue to production tag, with every step's evidence linked in its issue.
  This behavioural check is done the way a person would.

## Change impact

| Changed | Used by today | Breaks? | Mitigation / rollback |
|---|---|---|---|
| `main` → `production` in 5 repos | local clones, CI triggers, `auto_pr_target`, docs, open PRs | local clones lose their upstream; CI on `main` stops | rename printed commands; CI moved in the same change; GitHub redirects PRs and links; rename back to undo |
| Default branch → `develop` | `hq up` updates, `gh repo clone`, LangBrain autopilot | new clones start on `develop` (intended) | registry `default_branch` updated in the same change |
| ai-specs kit 0.2 (lint, roles, workflow) | LangBrain (0.1, no active changes) | no | 0.1 changes keep 0.1 rules; `init` upgrades |
| `/hq-spec`, `/hq-factory`, `/hq-ship`, `/hq-status`, `/hq-triage` | owner's daily flow | repos without `tracker = "github"` | `null` tracker keeps the job flow; OpenSpec mode without GitHub stays as today |
| `prereqs.py` (`gh` required for `hq`) | `hq up` on every machine with `hq` | `hq up` stops until `gh` is installed and logged in | apt package `gh` offered; the message gives `gh auth login` |
| Branch protections | any direct push, including the owner's | direct pushes fail | intended; PRs only; owner bypass for review count |

## Rollback

- **Code:** revert the merge commits in each repo.
- **GitHub:** `repo_setup --undo` removes the protections and workflow it created, renames `production` back to `main`
  and restores `main` as default. Labels and issues stay; they are harmless.
- **Kit:** pin the previous kit version and re-run `init`.
- No data migration is involved.
