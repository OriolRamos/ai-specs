# ADR-0005 · Approval card: approve from the issue, verified by the workflow run (kit 0.3.0)

- **Date:** 2026-11-16 · **Status:** accepted
- **Change:** `openspec/changes/visual-approval` (issue #8)

## Context
An approver could approve a change only with `ai-specs approve` in their own terminal, typing 8 characters of a digest
that says which bytes are approved but not what they say. Reviews happen on the GitHub web and mobile UI, so approvals
waited for a desk, and nothing on the issue showed the frozen scope in plain language.

## Decision
- **A card on the issue.** A kit workflow, `.github/workflows/ai-specs-approval.yml`, keeps one sticky bot comment on
  every open change issue, drawn from the change folder at the branch head: Why, What Changes, Not to add,
  requirements, human-gate tasks, sensitive paths, links at the commit, the short digest and one checkbox. A new
  digest redraws it unchecked and sends the issue back to `state:proposed`.
- **A tick is an approval only when the workflow can prove it.** The editor comes from the event
  (`sender.login`), never from comment text; it must be in `approvers` of the default branch's `roles.yaml`; the
  card's digest must equal the head's; and its scope text must equal a fresh render. Then the workflow posts
  `<!-- ai-specs:approval … by=<login> via=card run=<id> -->` with an @mention of the approver.
- **`check-approval` verifies the run.** A card record counts only when the Actions bot wrote it, it was never
  edited, and its run is an `issue_comment` run of the card workflow on the default branch triggered by the approver.
  `issue_comment` runs always use the default branch's workflow file, which only an approved, reviewed PR changes.
  Edited approval comments of either kind no longer count. The terminal approval stays as the fallback.
- **Least privilege and pins.** The card workflow asks for `contents: read` and `issues: write` only, uses
  `GITHUB_TOKEN` only, reads the change branch as data, and pins every action and the kit checkout to commit SHAs
  (`init` refuses without the kit's `v<VERSION>` tag). The `approval` job gains `actions: read`.

Rejected: GitHub Environments with required reviewers (no scope summary, paid on private repos, and the owner's token
approves them just the same) and PR reviews (GitHub forbids approving your own PR, and agents open PRs with the
owner's account).

## Consequences
- Approving takes one tick on any device, next to a plain-language summary of exactly what is approved.
- The honest limit does not move: agents act with the owner's token, so GitHub cannot tell an agent's tick from the
  owner's. The boundary is a guard on the agent's machine that denies those commands, which ships before `v0.3.0`;
  every card approval @mentions the approver, so one given in their name is noticed.
- Repos on kit 0.2.x ignore card records (their regex does not match them), so a card approval cannot pass an old gate.
  A repo takes the card with one size-S "adopt kit 0.3.0" change approved in the terminal.
- The card workflow has no `actions: read`, so the `state:approved` label it sets is advisory; `check-approval`
  stays the authority.
