# ADR-0002 · GitHub governs state, approval and releases (kit 0.2)

- **Date:** 2026-11-14 · **Status:** accepted
- **Change:** `openspec/changes/github-governed-flow` (approved at e860f90, digest
  `sha256:5c1dd0006d6c5ea0df2196d0603b7f178234e68e49217b352971476ae1de4da2`)

## Context
Kit 0.1 specified changes well, but their state, approval and history lived in a private orchestrator folder. Nothing
linked an issue to its spec, commits, PR and release. Branch models differed per repo. Contracts and impact existed
only on paper.

## Decision
- **GitHub carries the state.** It holds the state (issues with one `state:*` label), the approval (comments bound to
  a digest of the change, by approvers in `openspec/roles.yaml`, given by a person in their own terminal) and the
  release history (tags and releases on `production`). OpenSpec carries the intent.
- **Branches.** Every repo uses `develop → pre-production → production`, with protected branches, required checks
  `ai-specs`, `approval` and `gate`, and a hotfix path.
- **Contracts** are versioned and checked by pinned validators. Released versions are immutable.
- **Platforms.** A product with several repos gets a `<product>-platform` repo with a catalog and `ai-specs impact`.
- **Memory.** One canonical place per kind of memory (standard section 13).
- **Tooling.** The kit stays stdlib-only Python; GitHub access goes through `gh` only.

## Consequences
- Adopting repos need `gh` for approvals and CI, and Node for OpenSpec and the validators.
- Kit 0.1 repos keep linting clean. The 0.2 rules (roles, released contracts) apply after `init` upgrades them.
- Each repo's CI checks out the kit at tag `v<kit version>`. A kit release must therefore be tagged before repos run
  its workflow. A private kit repo needs the `AI_SPECS_TOKEN` secret in adopting repos.
