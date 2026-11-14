# ADR-0003 · Fixes from the end-to-end audit (kit 0.2.1)

- **Date:** 2026-11-14 · **Status:** accepted
- **Change:** `openspec/changes/audit-fixes`

## Context
An end-to-end rehearsal of the GitHub flow, together with a design review, found six defects:
- new capabilities failed strict validation after archive;
- hotfix back-merges could not pass the approval check;
- the private workspace was on the approval flow;
- dependency bots were either blocked or merged without control;
- the order of spec, tasks and approval was ambiguous;
- LangBrain's builders could build without approval.

## Decision
- Every delta spec carries a `## Purpose` of at least 50 characters. Lint requires it for new capabilities.
- `check-approval --pr` resolves the issue from `Closes #n`, or else from a `change/<n>-` or `hotfix/<n>-` head
  branch.
- The kit workflow skips only the approval job for `dependabot[bot]` and `renovate[bot]` PRs.
- Every builder runs `check-approval` first.
- The order is spec → tasks → approve → build.
- Private state repos use `tracker = "none"` on a single unprotected `main`.

## Consequences
Repos pick up kit 0.2.1 by re-running `init`, after the `v0.2.1` tag exists.
