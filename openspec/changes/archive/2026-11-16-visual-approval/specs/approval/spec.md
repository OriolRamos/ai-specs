## Purpose

Binds work to a human approval of the exact change scope and makes every path that builds or merges code check it.

## ADDED Requirements

### Requirement: ASP-117 — check-approval counts verified card approvals
`ai-specs check-approval` SHALL count a record carrying `via=card run=<id>` for its `by` login only when all of these
hold:
- its author is `github-actions[bot]` (type `Bot`);
- it was never edited (`created_at == updated_at`);
- `by` is in `approvers`;
- run `<id>` of this repository has event `issue_comment`, path `.github/workflows/ai-specs-approval.yml`, head branch
  equal to the default branch, triggering actor `by`, and was created no later than the comment.

Card and terminal approvals SHALL be counted together by distinct login. A record whose run is not found SHALL not
count (exit 1 when approvals are then missing). A failure to query GitHub SHALL be exit 2.

#### Scenario: Valid card approval passes the gate
- **GIVEN** issue 12 with digest D and a bot record `digest=D by=owner via=card run=77`, where run 77 is an
  `issue_comment` run of `ai-specs-approval.yml` on `develop` triggered by `owner`
- **WHEN** `ai-specs check-approval . 12` runs
- **THEN** it exits 0 and names `owner`
- **Proof:** `python3 -m unittest tests.test_approval.CardRecordTest.test_verified_card_record_counts` in ai-specs passes

#### Scenario: Record from a branch workflow is ignored
- **GIVEN** the same record but run 77 has event `push` on `change/12-demo`
- **WHEN** `ai-specs check-approval . 12` runs
- **THEN** the record is ignored and the check exits 1
- **Proof:** `python3 -m unittest tests.test_approval.CardRecordTest.test_run_event_path_branch_and_actor_must_match` in ai-specs passes

#### Scenario: Mixed sources reach min_approvals
- **GIVEN** `approvers: [a, b]`, `min_approvals: 2`, a terminal approval by `a` and a verified card approval by `b`, both for D
- **WHEN** `ai-specs check-approval . 12` runs
- **THEN** it exits 0 naming `a, b`
- **Proof:** `python3 -m unittest tests.test_approval.CardRecordTest.test_terminal_and_card_count_together` in ai-specs passes

#### Scenario: Run lookup fails
- **GIVEN** a card record and a GitHub API error on the run lookup
- **WHEN** `ai-specs check-approval . 12` runs
- **THEN** it exits 2 and nothing treats it as approved
- **Proof:** `python3 -m unittest tests.test_approval.CardRecordTest.test_run_lookup_error_is_exit_2` in ai-specs passes

### Requirement: ASP-118 — An edited approval comment does not count
`ai-specs check-approval` SHALL ignore any approval comment, terminal or card, whose `updated_at` differs from its
`created_at`.

#### Scenario: Record edited to a new digest
- **GIVEN** an approval comment for digest D later edited to say digest E, the current digest
- **WHEN** `ai-specs check-approval . 12` runs
- **THEN** the comment is ignored and the check exits 1
- **Proof:** `python3 -m unittest tests.test_approval.CardRecordTest.test_edited_records_are_ignored` in ai-specs passes
