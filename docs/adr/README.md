# Decisions about the method

| ADR | Where | Decision |
|---|---|---|
| ADR-0001 | [0001-standard-and-kit.md](0001-standard-and-kit.md) | ai-specs is a standard and a kit on top of OpenSpec, not an orchestrator |
| ADR-0002 | [0002-github-governed-flow.md](0002-github-governed-flow.md) | GitHub governs state, approval and releases (kit 0.2) |
| ADR-0003 | [0003-audit-fixes.md](0003-audit-fixes.md) | Purpose for new capabilities, PR-to-issue by branch, bot skip, builders check approval, data repos off the flow (kit 0.2.1) |
| ADR-0004 | [0004-brain-memory.md](0004-brain-memory.md) | Optional local brain per machine; it links to specs, ADRs and issues, never restates them (kit 0.2.2) |
| ADR-0005 | [0005-approval-card.md](0005-approval-card.md) | Approve from a plain-language card on the issue; `check-approval` verifies the workflow run behind each card record; edited approvals never count (kit 0.3.0) |

Decisions taken in the owner's private AI-HQ workspace that shaped the method (summarised here, the full text stays private):
ADR-013 neutral skills move to ai-skills · ADR-014 specs live in each repo with ai-specs · ADR-015 Linux only, modules per
machine · ADR-016 the method repos run the GitHub flow · ADR-017 private state repos stay off the approval flow · ADR-018 the guard follows the registry, work lands on develop · ADR-019 local working memory per machine (brain).
New method decisions are written here (standard section 13), never only in the workspace.
