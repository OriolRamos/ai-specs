# ai-specs · How a repo specifies, builds and closes every change

ai-specs is a **standard plus a kit** that you apply to a repo. It runs on [OpenSpec](https://github.com/Fission-AI/OpenSpec)
(MIT, pinned to 1.13.1). It fuses two things:
- **Governed platform specs:** living specs, deltas, stable requirement ids, contracts, approval of a frozen scope,
  and archive in the same PR.
- **Agent-driven delivery:** a proof for every scenario, "not to add", prior art, change impact, tasks sized for a
  fresh agent context, and the ceremony scaled to the size of the change.

The result is that a repo keeps its own memory (what it does today, why, and how each behaviour is proved), and
several people or agents can work on it without a private tool.

| Layer | Repo | Role |
|---|---|---|
| Method | ai-skills | How to debug and review (neutral skills) |
| **Standard** | **ai-specs** | **How a change is specified, proved and closed (this repo)** |
| Engine | ai-hq | Plans, runs and verifies changes autonomously across repos (optional) |
| State | a tracker | Backlog, owners, status, approvals: AI-HQ workspace, GitHub Issues or Azure Boards |

Read the standard first: [docs/standard.md](docs/standard.md). Why it is built this way: [docs/adr/0001-standard-and-kit.md](docs/adr/0001-standard-and-kit.md).

## Apply it to a repo

```bash
python3 <ai-specs>/scripts/ai_specs.py doctor <repo>               # what process the repo runs today
python3 <ai-specs>/scripts/ai_specs.py init <repo> --prefix LB     # once: config, folders, AGENTS.md block
```

`init` writes `openspec/config.yaml` (the kit's rules, which OpenSpec passes to the agent for every artifact),
creates `openspec/specs/` and `openspec/changes/`, and adds a managed block to the repo's `AGENTS.md` (or
`CLAUDE.md`). Re-running it upgrades the repo to the current kit. It **refuses** a repo that already runs another
process: an `openspec/config.yaml` not written by ai-specs, or an Azure DevOps process skill. Company repos keep
their own process.

Nothing is migrated. `openspec/specs/` fills up as changes are archived.

## A change, by hand

```bash
openspec new change add-greeting                                     # or: npx -y @fission-ai/openspec@1.13.1 ...
python3 <ai-specs>/scripts/ai_specs.py scaffold <repo> add-greeting --size S --capability greeting
# fill proposal.md, specs/greeting/spec.md and tasks.md (replace every TODO)
openspec validate add-greeting --strict
python3 <ai-specs>/scripts/ai_specs.py lint <repo> add-greeting
# implement task by task; when all are done and the repo's gate is green, in the same PR:
openspec archive add-greeting --yes
```

With AI-HQ, `/hq-spec`, `/hq-tickets` and `/hq-factory` do this for you when the repo runs ai-specs.

## Changing the kit without breaking repos

- Repos record the kit version in `openspec/config.yaml`. `doctor` says when a repo is outdated, and `init`
  upgrades it.
- New lint rules must accept everything that is already archived. Lint only checks **active** changes, never
  `archive/` or `specs/`.
- `kit/config.yaml.tmpl` rules must be single-quoted YAML scalars. OpenSpec ignores a config it cannot parse, so
  a test guards this.
- Before merging: `python3 -m unittest discover -s tests`. Before a release: run the end-to-end check in
  `CLAUDE.md` with the real OpenSpec CLI. Bump `VERSION` whenever the kit changes.

## Layout

```
docs/standard.md          the standard (what is required and why)
docs/adr/                 decisions about the standard
kit/config.yaml.tmpl      OpenSpec config written into each repo
kit/agents-block.md       managed block for the repo's AGENTS.md / CLAUDE.md
kit/templates/            scaffold templates (design, tasks, spec)
scripts/ai_specs.py       init · scaffold · lint · doctor (stdlib only)
tests/                    CLI tests
```
