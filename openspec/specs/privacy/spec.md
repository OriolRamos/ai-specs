# privacy Specification

## Purpose
Keeps internal names and knowledge on the machine they belong to, checked locally before anything is pushed or published.

## Requirements

### Requirement: ASP-090 — Local leak check before anything leaves the machine
When `~/.config/ai-specs/forbidden-terms.txt` exists, `ai-specs leak-check <repo>` SHALL report every tracked file (or,
with `--range A..B`, every file changed in that range) containing one of its terms, case-insensitively, and exit 1;
`ai-specs lint` SHALL include it; AI-HQ's guard SHALL run it on every `git push` from a registered repo or to a GitHub
remote, in the folder the command actually runs in (following `cd`), over the commits being pushed, and deny the push
naming the files; a repo pushing to its own company server is not checked, since it legitimately holds those names; the
terms SHALL never be written to a repo, a workflow or a log.

#### Scenario: A push that names the company is denied
- **GIVEN** a terms file listing a company name and a commit adding that name to a markdown file
- **WHEN** the agent runs `git push` for that branch
- **THEN** the guard denies it naming the file, and the term does not appear in the message
- **Proof:** `python3 -m unittest tests.test_guard_registry.LeakPushTest` in ai-hq passes

#### Scenario: Range scan
- **GIVEN** a term present in an old commit and absent from the range `A..B`
- **WHEN** `ai-specs leak-check . --range A..B` runs
- **THEN** it exits 0
- **Proof:** `python3 -m unittest tests.test_leakcheck` in ai-specs passes
