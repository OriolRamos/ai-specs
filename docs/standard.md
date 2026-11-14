# The ai-specs standard

How a repo describes what it does and how every change to it is specified, built, proved and closed. It runs on
[OpenSpec](https://github.com/Fission-AI/OpenSpec) (MIT) and fuses two ways of working:

- **Governed platform specs** (living specs, deltas, stable requirement ids, contracts with conformance, frozen scope,
  archive in the same PR) — memory and traceability for several people over years.
- **Agent-driven delivery** (reference result and proof per criterion, "not to add", prior art, change impact,
  tickets sized for a fresh context, evidence, human gate) — so an orchestrator can build it autonomously and
  nobody has to trust "it works".

## Contents
1. Where things live
2. Size decides the ceremony
3. Proposal
4. Delta specs (requirements and scenarios)
5. Design
6. Tasks
7. Contracts
8. Lifecycle: propose → approve → apply → archive
9. What stays out of the repo
10. Checks

## 1. Where things live

| What | Where | Lifetime |
|---|---|---|
| What the system does **today** | `openspec/specs/<capability>/spec.md` | Living: updated by every archived change |
| One change in flight | `openspec/changes/<id>/` (proposal, specs, design, tasks) | Until archived |
| Change history | `openspec/changes/archive/<date>-<id>/` | Forever |
| Machine contracts | `contracts/<name>/v<N>/` (OpenAPI / JSON Schema + examples) in the **provider** repo | Versioned |
| Repo decisions | the repo's ADR folder (`docs/adr/` or `.agents/memory/decisions.md`) | Forever |
| Operational state: backlog, owner, status, approvals, logs, evidence of runs | the orchestrator or tracker (AI-HQ workspace, GitHub Issues, Azure Boards…) | Outside the repo |

OpenSpec keeps intent, requirements, design and tasks. The tracker keeps state. Neither copies the other: a work
item links the change; the change never holds a status field.

## 2. Size decides the ceremony

Every proposal starts with `**Size:** S`, `M` or `L`. The size sets what is required, so a one-line fix does not
cost what an epic costs.

| Size | Typical | Required |
|---|---|---|
| **S** | one sitting, one repo, no contract or data change | proposal (Why, What Changes, Not to add) + tasks; delta specs when observable behaviour changes |
| **M** | 1–3 task groups, or a contract or schema change in one repo | S + Prior art and reuse + Change impact |
| **L** | several repos, data migration, security-sensitive, or an epic | M + `design.md` (with the Change impact table) |

## 3. Proposal (`proposal.md`)

```markdown
**Size:** M

## Why
What happens today, who it affects, why now (3–6 lines).

## What Changes
- Observable changes, affected capabilities, modules, interfaces, data and docs.
- **Excludes:** concrete non-goals.

## Not to add
What an agent might add unasked (extra endpoints, flags, auth factors, config options, "hardening" that changes
a requirement). Any of these needs a new decision. "Nothing specific" is valid for S.

## Prior art and reuse            (M, L)
What already exists (this repo, sibling repos, packages, skills) and the decision: reuse / extend / build new.
New dependencies are proposals for the owner, never silent.

## Change impact                  (M; for L it lives in design.md)
| Changed (symbol / endpoint / table / event) | Used by today | Breaks? | Mitigation / rollback |
```

## 4. Delta specs (`specs/<capability>/spec.md`)

- One **observable** behaviour per Requirement, with **SHALL** or **MUST**.
- Title: `### Requirement: <PREFIX>-NNN — <name>`. The id is unique in the repo and never reused or renumbered
  after archive. The prefix is set per repo at `init` (e.g. `LB`).
- At least one `#### Scenario:` per Requirement with **GIVEN / WHEN / THEN**. THEN states a **reference result**
  (exact status and body, exact CLI output, a screenshot path for UI), never "it works".
- Every Scenario ends with **`- **Proof:**`**: the command or test that demonstrates it and what counts as a pass.
  The proof survives archive, so the living spec says how each behaviour is checked.
- Link contracts instead of copying OpenAPI or JSON Schema into Markdown.
- Use `## ADDED`, `## MODIFIED`, `## REMOVED` or `## RENAMED Requirements` exactly as OpenSpec expects. A MODIFIED
  requirement is copied whole and edited, keeping its id.

```markdown
### Requirement: LB-014 — Recipe runs refuse a dirty worktree
A recipe run SHALL stop before its first step when the target worktree has uncommitted changes.

#### Scenario: Dirty worktree
- **GIVEN** a registered repo whose worktree has one modified file
- **WHEN** `recipe_implement_ticket` starts on it
- **THEN** it returns `{"status": "blocked", "reason": "dirty_worktree"}` and changes no file
- **Proof:** `pytest tests/test_recipes.py::test_dirty_worktree_blocks` passes
```

## 5. Design (`design.md`, required for L)

Context, decisions with the alternatives rejected, compatibility and migration, security, operations, test strategy,
**Change impact** table and **rollback** (how to undo: revert, plus any data or migration step). Distinguish editable
sources from derived artifacts.

## 6. Tasks (`tasks.md`)

Checkboxes only, grouped by numbered sections, updated while building. Each task is a **vertical slice in one repo
that fits a fresh agent context** (about ≤ 400 changed lines and ≤ 8 files; split otherwise) and carries its proof:

```markdown
## 2. Dirty worktree guard
- [ ] 2.1 Block recipe runs on a dirty worktree — test first: `tests/test_recipes.py::test_dirty_worktree_blocks` — proof: `pytest -q tests/test_recipes.py`
```

- `test first` names the test that must fail before the code exists (`n/a` only for docs or config).
- `proof` is the command whose output shows the task is done.
- Order: baseline → contracts (provider before consumer) → behaviour → docs → removal of replaced sources.
- A task touching a sensitive path the repo declares is marked `(human gate)`.

## 7. Contracts

When two repos or modules talk, the **provider** owns a versioned contract (`contracts/<name>/v<N>/`: OpenAPI or JSON
Schema, a valid example and negative examples) and a conformance test in its CI. The consumer mirrors or generates
types from it and never adds fields the provider does not return. Breaking changes create `v<N+1>`. For a product
made of several repos, a small governance repo (catalog of capabilities, interfaces and modules + contracts) is
worth it only when three or more repos share contracts.

## 8. Lifecycle

1. **Propose.** `openspec new change <id>`, then fill the artifacts the size requires. Check:
   `openspec validate <id> --strict` and `ai_specs.py lint <repo> <id>`.
2. **Approve.** A person approves the proposal (PR review, or the orchestrator's human gate). The approval records
   the commit of the change folder; editing the scope afterwards needs a new approval.
3. **Apply.** Tasks in order, one fresh context each; tick them as they pass their proof. Scope changes go back to
   the proposal, never silently into code.
4. **Archive.** When every task is done and the repo's gate is green: `openspec archive <id> --yes` **in the same
   PR**, so `openspec/specs/` and the code merge together.

## 9. What stays out of the repo

Status fields, owners, dates of approval, run logs, chat transcripts, business or personal context, secrets.
They belong to the tracker or the orchestrator's private workspace.

## 10. Checks

| Check | Command | Blocks |
|---|---|---|
| OpenSpec structure | `openspec validate <id> --strict` | yes |
| ai-specs rules (size, sections, ids, proof, task format) | `python <ai-specs>/scripts/ai_specs.py lint <repo> [<id>]` | yes |
| Repo health and which `openspec` command to use | `python <ai-specs>/scripts/ai_specs.py doctor <repo>` | no |
