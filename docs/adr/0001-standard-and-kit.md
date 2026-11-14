# ADR-0001 · ai-specs is a standard and a kit on top of OpenSpec, not an orchestrator

- **Date:** 2026-11-14 · **Status:** accepted

## Context
Two ways of specifying work were in use:
- **Governed platform specs** (OpenSpec with living specs, deltas, requirement ids, versioned contracts with
  conformance tests, scope approved and frozen, archive in the same PR, operational state in a tracker). This gives
  strong memory and traceability, but every change costs the same ceremony and the tasks are written for people.
- **AI-HQ jobs** (`SPEC.md` + `TICKETS.md` in a private workspace). Each acceptance criterion has a reference result
  and a proof, there are "not to add" and prior-art sections, tickets are sized for an agent, and a factory builds
  and reviews them. But there are no living specs: when a job closes, its knowledge stays in a private folder, out
  of the repo. Requirements have no stable ids and no validator.

The goal was more memory, traceability and stability with several people, while keeping autonomous delivery.

## Decision
- A separate repo, **ai-specs**, holds the **standard** (`docs/standard.md`) and a **kit** that applies it to any
  repo: an OpenSpec config with the rules, scaffold templates, and a stdlib CLI (`init`, `scaffold`, `lint`,
  `doctor`).
- **OpenSpec is the format** (MIT, pinned version). The fusion is expressed as OpenSpec config rules, which reach
  the agent through `openspec instructions`, plus a lint for what OpenSpec does not check: size line, required
  sections per size, requirement id prefix, a `Proof:` line per scenario, and the task format.
- **Size S/M/L** scales the ceremony.
- ai-specs is **not an orchestrator**. AI-HQ stays the engine and gains an OpenSpec mode for repos that run ai-specs.
  Operational state stays in a tracker: the AI-HQ workspace now, GitHub Issues later.
- Patterns are rebuilt from public sources. No company tooling, text or templates are copied.
- `init` refuses repos that already run another spec process.

## Consequences
- Specs live with the code, and anyone can read or validate them without AI-HQ.
- Adopting repos need OpenSpec (Node) to validate and archive. `doctor` prints the pinned `npx` command when it is
  not installed.
- The kit can evolve: repos record the kit version, lint checks only active changes, and `init` upgrades in place.
- Existing AI-HQ jobs are not migrated. Repos without ai-specs keep the job flow.
