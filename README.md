# ai-specs · How a repo specifies, approves, builds, releases and remembers every change

ai-specs is a **standard plus a kit** that you apply to a repo. It runs on [OpenSpec](https://github.com/Fission-AI/OpenSpec)
(MIT, pinned to 1.13.1) and GitHub. It fuses:

- **Governed platform work:**
  - living specs, deltas and stable ids;
  - an issue → spec → commit → PR → release chain;
  - human approval of a frozen scope;
  - `develop → pre-production → production`;
  - versioned contracts with conformance, a product catalog with impact, one gate per repo.
- **Agent-driven delivery:** a proof for every scenario, "not to add", prior art, change impact, tasks sized for a fresh
  agent context, and ceremony scaled to the size of the change.

| Layer | Repo | Role |
|---|---|---|
| Method | ai-skills | How to debug and review (neutral skills) |
| **Standard** | **ai-specs** | **How a change is specified, approved, proved, released and remembered (this repo)** |
| Engine | ai-hq | Plans, runs and verifies changes autonomously across repos (optional) |
| State | GitHub | Issues, approvals, PRs, releases |

Read the standard first: [docs/standard.md](docs/standard.md). Decisions: [docs/adr/](docs/adr/).

## Apply it to a repo

```bash
ai-specs doctor <repo>                                   # what process the repo runs today
ai-specs init <repo> --prefix LB --owner <github-login> --gate "<the repo's gate command>"
ai-specs init <repo> --prefix SHOP --owner <login> --platform   # a product platform repo (catalog, contracts, ADRs)
```

`ai-specs` is `scripts/ai_specs.py`: AI-HQ links it to `~/.local/bin`, or you can run it with `python3`.

`init` writes the following:
- **`openspec/config.yaml`:** the kit's rules, which OpenSpec passes to the agent;
- **`openspec/roles.yaml`:** the approvers, reviewers and releasers;
- **the `openspec/specs/` and `openspec/changes/` folders;**
- **a managed block in `AGENTS.md` or `CLAUDE.md`;**
- **`.github/workflows/ai-specs.yml`:** the required checks `ai-specs`, `approval` and `gate`;
- **`.github/workflows/ai-specs-approval.yml`:** the approval card (below).

Both workflows pin every action and the kit checkout to commit SHAs: `init` reads the commit of the kit's `v<VERSION>`
tag and refuses when the tag is missing (`git -C <kit> fetch --tags`).

Re-running it upgrades the repo to the current kit and keeps its gate. It **refuses** a repo that already runs
another process. Nothing is migrated: `openspec/specs/` fills up as changes are archived.

Branches, protections and labels on GitHub are applied by AI-HQ's `repo_setup.py`, or by hand following section 9 of
the standard.

## A change, by hand

```bash
# 1. issue #12 with type:change, size:S, state:proposed; branch change/12-add-greeting from develop
openspec new change add-greeting
ai-specs scaffold . add-greeting --size S --capability greeting      # fill every TODO
openspec validate add-greeting --strict && ai-specs lint . add-greeting
git push; ai-specs digest . add-greeting                            # write the managed block on the issue
# 2. the approver ticks the approval card on issue #12 (web or mobile), or, in their own terminal:
ai-specs approve . 12
# 3. build: ai-specs check-approval . 12 must pass; commits "Refs #12"; tick tasks as proofs pass
# 4. openspec archive add-greeting --yes; PR into develop with "Closes #12"; CI: ai-specs, approval, gate
```

With AI-HQ, `/hq-spec`, `/hq-approve`, `/hq-factory` and `/hq-ship` do these steps. The approval itself is always a
person's.

## The approval card

Once the branch is pushed, the card workflow keeps one comment on the issue that says in plain language what the
digest stands for: Why, What Changes and Not to add, the requirement ids and titles, the human-gate tasks, the
sensitive paths named, links to every artifact at the exact commit, and one box:
`- [ ] I approve exactly this scope (digest 1a2b3c4d)`. An approver ticks it; the workflow checks that the editor is in
`approvers`, that the digest is still the head's and that the card text was not changed, then posts an approval record
that @mentions the approver and sets `state:approved`. Any other tick is undone with the reason. A push that changes
the scope redraws the card unchecked and moves the issue back to `state:proposed`. To revoke a card approval, delete
its record comment. `check-approval` counts a card record only when the run that wrote it was an `issue_comment` run
of the default branch's card workflow triggered by the approver, and never counts an edited approval comment.

## Other commands

| Command | Does |
|---|---|
| `ai-specs contract new <repo> <name> --kind jsonschema\|openapi` | contract `v1` skeleton with valid and invalid examples |
| `ai-specs contract check <repo>` | conformance with pinned ajv / redocly through npx (`AI_SPECS_NPX` overrides the runner) |
| `ai-specs catalog check <platform>` · `ai-specs impact <platform> <id>` | product catalog checks; what an id touches |
| `ai-specs adr new <repo> "<title>"` | next numbered ADR in `docs/adr/` |
| `ai-specs check-approval <repo> <issue>\|--pr <n>` | 0 approved, 1 missing or stale, 2 cannot check |
| `ai-specs card resolve\|render\|review <repo> --event <file> --src <dir>` | the approval card workflow's steps |

## Changing the kit without breaking repos

- **Versions.** Repos record the kit version in `openspec/config.yaml`. `doctor` says when a repo is outdated, and
  `init` upgrades it.
- **Rules.** New lint rules apply only from the kit version that introduces them, and lint only checks **active**
  changes.
- **YAML.** Rules in `kit/config.yaml.tmpl` must be single-quoted YAML scalars, because OpenSpec ignores a config it
  cannot parse. A test guards this.
- **Release tag.** Adopting repos check the kit out at the commit of tag `v<VERSION>` in CI, and `init` needs that
  tag in the kit checkout, so a kit release must be tagged on `production` before repos re-run `init`.
- **Before merging:** `python3 -m unittest discover -s tests` and `bash scripts/e2e.sh`. CI runs both as this repo's
  gate.

## Layout

```
docs/standard.md          the standard
docs/adr/                 decisions about the standard
kit/                      config.yaml.tmpl, agents-block.md, workflow.yml.tmpl, approval-card.yml.tmpl, templates/
scripts/ai_specs.py       CLI: init · scaffold · lint · doctor · digest · approve · check-approval · card ·
                          contract · catalog · impact · adr
scripts/card.py           the approval card: render, follow the head, review a tick
scripts/approval.py       digest, roles, approval      scripts/contracts.py   contracts
scripts/catalog.py        platform catalog, impact     scripts/ghcli.py       the only GitHub access (gh)
scripts/e2e.sh            end to end with the real OpenSpec CLI
tests/                    unit tests (fake gh, fake validators)
openspec/                 this repo's own specs and changes (prefix ASP)
```
