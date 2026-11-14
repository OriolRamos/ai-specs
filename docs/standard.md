# The ai-specs standard (0.2)

How a repo describes what it does, and how every change to it is specified, approved, built, proved, released and
remembered. It runs on [OpenSpec](https://github.com/Fission-AI/OpenSpec) (MIT) and GitHub, and it fuses two ways of
working:

- **Governed platform work:**
  - living specs, deltas and stable requirement ids;
  - a visible issue → spec → commit → PR → release chain;
  - human approval of a frozen scope;
  - `develop → pre-production → production`;
  - versioned contracts with conformance, a product catalog with impact, one gate per repo.
- **Agent-driven delivery:**
  - a proof for every scenario;
  - "not to add", prior art and change impact;
  - tasks sized for a fresh context;
  - ceremony scaled to the size of the change.

## Contents
1. Where things live
2. Size decides the ceremony
3. Proposal
4. Delta specs (requirements and scenarios)
5. Design
6. Tasks
7. Issues, states and traceability
8. Roles and approval
9. Branches, releases and hotfixes
10. Contracts
11. Product platform, catalog and impact
12. Quality gate
13. Memory
14. Lifecycle
15. Checks

## 1. Where things live

| What | Where |
|---|---|
| What the system does **today** | `openspec/specs/<capability>/spec.md` (living: updated by every archived change) |
| One change in flight | `openspec/changes/<id>/` (proposal, specs, design, tasks) |
| Change history | `openspec/changes/archive/<date>-<id>/`, closed issues, GitHub releases |
| State, owner, approval of a change | its GitHub issue (labels, managed block, approval comments) |
| Who may approve, review, release | `openspec/roles.yaml` |
| Machine contracts | `contracts/<name>/v<N>/` in the provider repo, or in the product platform repo when shared |
| Product map | `catalog/product.json` in the `<product>-platform` repo |
| Decisions | `docs/adr/` (see 13. Memory) |
| CI | `.github/workflows/ai-specs.yml` (written by `init`) |

OpenSpec keeps the intent. The issue keeps the state. Neither copies the other: the issue links the change, and the
change never holds a status field.

## 2. Size decides the ceremony

Every proposal starts with `**Size:** S`, `M` or `L`.

| Size | Typical | Required |
|---|---|---|
| **S** | one sitting, one repo, no contract or data change | proposal (Why, What Changes, Not to add) + tasks; delta specs when observable behaviour changes |
| **M** | 1–3 task groups, or a contract or schema change in one repo | S + Prior art and reuse + Change impact |
| **L** | several repos, data migration, security-sensitive, or an epic | M + `design.md` (with the Change impact table and rollback) |

Every size goes through the issue, approval and PR flow. Size only changes how much has to be written.

## 3. Proposal (`proposal.md`)

```markdown
**Size:** M

## Why
What happens today, who it affects, why now (3–6 lines).

## What Changes
- Observable changes, affected capabilities, modules, interfaces, data and docs.
- **Excludes:** concrete non-goals.

## Not to add
What an agent might add unasked. Any of these needs a new decision.

## Prior art and reuse            (M, L)
Reuse / extend / build new, and why. New dependencies are proposals for the owner, never silent.

## Change impact                  (M; for L it lives in design.md)
| Changed | Used by today | Breaks? | Mitigation / rollback |
```

In a product with a catalog, the Change impact table starts from `ai-specs impact <platform> <id>`.

## 4. Delta specs (`specs/<capability>/spec.md`)

- One **observable** behaviour per Requirement, with **SHALL** or **MUST**.
- Title: `### Requirement: <PREFIX>-NNN — <name>`. The id is unique in the repo and never reused or renumbered.
- At least one `#### Scenario:` with **GIVEN / WHEN / THEN**. THEN states an exact **reference result**.
- Every Scenario ends with **`- **Proof:**`**: the command or test that demonstrates it and what counts as a pass. The
  proof survives archive, so the living spec says how each behaviour is checked.
- Link contracts; never copy OpenAPI or JSON Schema into Markdown.
- `## ADDED`, `## MODIFIED`, `## REMOVED` or `## RENAMED Requirements`, as OpenSpec expects.

## 5. Design (`design.md`, required for L)

Cover these points:
- context;
- decisions, with the alternatives rejected;
- compatibility and migration;
- security and operations;
- test strategy, including one behavioural check done the way a person would;
- the **Change impact** table and **rollback**.

## 6. Tasks (`tasks.md`)

Tasks are checkboxes only, grouped by numbered sections and ticked while building. Each task is a **vertical slice in
one repo that fits a fresh agent context** (about ≤ 400 changed lines, ≤ 8 files):

```markdown
- [ ] 2.1 Block recipe runs on a dirty worktree — test first: `tests/test_recipes.py::test_dirty_worktree_blocks` — proof: `pytest -q tests/test_recipes.py`
```

- **Order:** baseline → contracts (provider before consumer) → behaviour → docs → removal of replaced sources.
- **Human gate:** sensitive-path tasks are marked `(human gate)`.
- **Approval:** ticking a task never invalidates it; rewording one does.

## 7. Issues, states and traceability

- **One issue per change**, labelled `type:change` and `size:S|M|L`, in the repo that changes. Its body holds a
  managed block that only the tools rewrite:
  ```
  <!-- ai-specs:change -->
  change: <id>
  branch: change/<issue>-<slug>
  size: M
  spec_commit: <sha>
  digest: sha256:<hex>
  <!-- /ai-specs:change -->
  ```
- **One state label at a time:** `state:proposed` → `state:approved` → `state:in-progress` → `state:in-review` →
  closed (by the PR's `Closes #n`), plus `state:blocked` with a comment saying why. A scope edit after approval sends
  the issue back to `state:proposed`.
- **Epics:** work across repos has a `type:epic` issue in the product platform repo, with one `type:change` sub-issue
  per repo. The epic closes only when all its sub-issues are closed.
- **The chain:**
  1. the branch is `change/<issue>-<slug>`, created from `develop`;
  2. every commit carries the trailer `Refs #<issue>`;
  3. the PR into `develop` says `Closes #<issue>` and links the change folder;
  4. the release PR and the GitHub release list every issue closed since the previous tag.

## 8. Roles and approval

`openspec/roles.yaml` (GitHub logins):

```yaml
approvers: [owner-login]
reviewers: [owner-login]
releasers: [owner-login]
min_approvals: 1
```

- **`ai-specs digest <repo> <id>`** prints `sha256:` over the change folder:
  - files sorted by relative path; each contributes its path, a NUL byte and its content;
  - CRLF is normalised to LF, and task ticks to `- [ ]`;
  - the change is found live or in the archive.
- **`ai-specs approve <repo> <issue>`.**
  - Requirements: a person listed in `approvers`, running it **in their own terminal**. It refuses inside agent
    sessions (`CLAUDECODE`) and without a TTY.
  - Steps: it shows the digest and asks for its first 8 characters, posts
    `<!-- ai-specs:approval digest=… commit=… by=<login> -->`, and sets `state:approved`.
- **`ai-specs check-approval <repo> <issue> | --pr <n>`**
  - **Exit 0:** `min_approvals` distinct approvers approved the **current** digest, each in a comment written by
    themselves.
  - **Exit 1:** approvals are missing or stale.
  - **Exit 2:** it cannot check. Nothing treats 2 as approved.
- **Gates:** work does not start, and the PR into `develop` does not merge, until `check-approval` passes. CI runs it
  as the required `approval` check.
- **Agents** never approve, never merge into `develop`, `pre-production` or `production`, and never push to them.

## 9. Branches, releases and hotfixes

| Branch | Accepts | Required checks |
|---|---|---|
| `develop` (default) | PRs from `change/*`, `hotfix/*` | `ai-specs`, `approval`, `gate` + 1 review by a reviewer |
| `pre-production` | release PRs from `develop`, back-merges from `hotfix/*` | `ai-specs`, `gate` |
| `production` | promotion PRs from `pre-production`, PRs from `hotfix/*` | `ai-specs`, `gate` |

- **No direct pushes** to any of the three branches.
- **Release:** a PR from `develop` to `pre-production`, whose body is the changelog since the last tag.
- **Promotion:** a PR from `pre-production` to `production`. After a releaser merges it, an annotated tag `vX.Y.Z`
  and a GitHub release with the same notes are created.
- **Hotfix:** branch `hotfix/<issue>-<slug>` from `production`. Its PR goes into `production`, then back-merge PRs go
  into `pre-production` and `develop`. The issue stays open until both back-merges are in.

## 10. Contracts

```
contracts/<name>/v<N>/
  schema.json | openapi.yaml       # exactly one
  examples/valid/*.json            # must validate (at least one)
  examples/invalid/*.json          # must fail (at least one, JSON Schema)
  README.md                        # provider, consumers, compatibility notes
```

- **`ai-specs contract new <repo> <name> --kind jsonschema|openapi`** creates `v1`.
- **`ai-specs contract check <repo>`** validates every example with `ajv-cli@5.0.0` and lints OpenAPI with
  `@redocly/cli@1.34.5`, both pinned through `npx`. CI runs it.
- **A released version** (present on `origin/production`) is **immutable**: `lint` fails on any edit to it. Breaking
  changes create `v<N+1>`.
- **The provider** owns the contract. Consumers never add fields the provider does not return.

## 11. Product platform, catalog and impact

A product with two or more repos sharing a contract has a `<product>-platform` repo, created with
`ai-specs init <repo> --prefix <P> --platform`. It holds:

- `catalog/product.json`: modules, capabilities (owner, modules, specs), interfaces (contract, provider, consumers),
  data (owner, writers, readers);
- the shared contracts;
- cross-repo ADRs in `docs/adr/`;
- the product's epics.

Two commands work on it:
- **`ai-specs catalog check <platform>`** fails on duplicated ids, unknown modules and missing paths.
- **`ai-specs impact <platform> <id>`** lists what references a module, capability, interface, data asset or contract.

## 12. Quality gate

- **One command per repo.** It is declared in its README, in `init --gate "<command>"` and, under AI-HQ, in the
  registry. It runs the format check, lint, typecheck where the language has one, and the tests, and exits non-zero on
  any failure. Thresholds belong to the repo.
- **The kit workflow** runs three required checks: `ai-specs` (OpenSpec `validate --all --strict`, `ai-specs lint`,
  `contract check`), `approval` (PRs into `develop` and from `hotfix/*`) and `gate`. It asks only for read
  permissions.

## 13. Memory

| What | Canonical place |
|---|---|
| Behaviour today and how it is proved | `openspec/specs/` |
| Why and when it changed | the archive, closed issues and releases |
| Repo decisions | `docs/adr/NNNN-*.md` in the repo (`ai-specs adr new <repo> "<title>"`) |
| Cross-repo decisions | `docs/adr/` in the product platform repo; the ai-specs repo for the method itself |
| Private notes, lessons, taste | the owner's private workspace; never the only place a decision lives |
| Regenerable context | `.agents/memory/`, which can always be rebuilt from the above |

A lesson that repeats becomes a `type:change` issue in the repo that should hold the rule, and goes through the same
approval. No rule enters a repo outside a reviewed PR.

## 14. Lifecycle

1. **Issue.** Open it with `type:change`, `size:*` and `state:proposed`. For several repos, open an epic in the
   platform repo with one sub-issue per repo.
2. **Propose.**
   - Create branch `change/<issue>-<slug>` from `develop`.
   - Run `openspec new change <id>`, then fill what the size requires.
   - Check: `openspec validate <id> --strict` and `ai-specs lint <repo> <id>`.
   - Push, and write the managed block (spec commit and digest).
3. **Approve.** An approver reviews the change at that commit and runs `ai-specs approve`. Editing the scope later
   needs a new approval.
4. **Apply.**
   - Gate: `check-approval` must pass.
   - Move the issue to `state:in-progress`.
   - Build in task order, one fresh context per task. Commits carry `Refs #<issue>`; tick tasks as their proofs pass.
5. **Review.**
   - Gate: `check-approval` must pass again.
   - Run `openspec archive <id> --yes` on the same branch.
   - Open a PR into `develop` with `Closes #<issue>` and move the issue to `state:in-review`.
   - Required checks green, then a reviewer approves and merges. Merging closes the issue.
6. **Release.** Open a release PR `develop → pre-production`. After validation, open a promotion PR
   `pre-production → production`. A releaser merges each one. Then tag `vX.Y.Z` and publish the GitHub release.

## 15. Checks

| Check | Command | Blocks |
|---|---|---|
| OpenSpec structure | `openspec validate --all --strict` | yes (CI `ai-specs`) |
| ai-specs rules (size, sections, ids, proof, tasks, roles, released contracts) | `ai-specs lint <repo>` | yes (CI `ai-specs`) |
| Contract conformance | `ai-specs contract check <repo>` | yes (CI `ai-specs`) |
| Approved scope | `ai-specs check-approval <repo> --pr <n>` | yes (CI `approval`) |
| Repo gate | the repo's gate command | yes (CI `gate`) |
| Catalog | `ai-specs catalog check <platform>` | yes in platform repos |
| Repo health, process, kit version | `ai-specs doctor <repo>` | no |
