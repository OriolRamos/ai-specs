## Context

- **Memory kinds the flow already holds well:** specs, ADRs, issues and PRs, regenerable repo memory.
- **What is missing:** working knowledge that survives sessions, can be searched fast, is linked as a graph, and is
  shared or kept private on purpose.
- **What the owner asked for:** topic-specific stores whose documents link to each other (graph) with RAG-speed
  retrieval.
- **RSC Brain v0.7.0 provides:**
  - journal, proposals and wiki;
  - typed links and a graph view;
  - BM25 plus `pgvector` fused by rank, with Ollama embeddings;
  - brains with roles;
  - repo → brain resolution and Claude Code hooks;
  - MCP and an HTTP API;
  - Docker, PostgreSQL 17 and Node 25.
- **Limit that shapes the design:** relations and pages are scoped to one brain, so links do not cross brains.

## Decisions

### D0 · One local installation per machine, no sync
Each machine runs its own RSC Brain on localhost and holds only the brains of the work done on it. Nothing is
replicated between machines.

| Machine | Brains | Linked repos (by git remote) |
|---|---|---|
| Work machine | `work` (one topic per company repo, e.g. `<repo-a>/…`, `<repo-b>/…`) | the company repos under `~/develop` |
| Personal machine | `personal`, `method`, `langbrain`, `clothy` | the personal repos under `~/personal-assistant` |

The company brain lives only on the work machine and the personal brains only on the personal one.

### D1 · Topics are namespaces inside a brain; brains are sharing boundaries
The owner's "one store per topic" goal is served by **topic namespaces** (`<area>/<topic>`, the brain's own topic
keys) with one **index page per topic** linking its pages. Retrieval can be scoped to a topic, and the graph stays
connected across topics, so multi-hop questions such as "factory → reviewers → security policy" still work.
**Separate brains** are created only where the readers differ:

| Brain | Machine | Readers | Holds |
|---|---|---|---|
| `work` | work | owner | company repos: architecture, contracts, conventions, attempts, reasons; links to their specs, ADRs and work items |
| `personal` | personal | owner only | lessons, taste, private notes, cross-project know-how |
| `method` | personal | owner (later: people who adopt ai-specs) | how ai-specs, ai-skills and ai-hq work and why |
| `langbrain` | personal | owner (later: contributors) | LangBrain's domain, design reasons, attempts |
| `clothy` | personal | owner (later: the Clothy team) | product, clients, integrations |

*Rejected:* one brain per topic. It splits the graph, and cross-topic links would become plain URLs that the graph
cannot traverse.

### D2 · Hybrid retrieval, local only, in one database
- **Store:** RSC Brain's "existing PostgreSQL" install option points at a local **ParadeDB** container (PostgreSQL
  17 with `pg_search` and `pgvector` preinstalled). Text, vectors (HNSW index), graph and permissions live in one
  database, with one backup. *Rejected:* a separate vector store (Qdrant, Weaviate, Chroma, LanceDB). It adds a
  second system to secure and back up for no gain at thousands of pages; it would only make sense for a separate RAG
  over large static corpora.
- **Search:** BM25 (`pg_search`) plus meaning search (`pgvector`), fused by reciprocal rank, so a page found both ways
  ranks first. Superseded pages rank below their replacements.
- **Embeddings:** Ollama `nomic-embed-text` on the same machine. Text never leaves it.
- **Fallback:** without the extensions or Ollama, RSC Brain keeps word search. That degrades quality, not
  availability.

### D12 · Repo `ai-brain`: one manager per machine, with sharing policies
`ai-brain` is standalone, like ai-skills: it runs on the work machine without AI-HQ. Its CLI, `ai-brain`, is stdlib
Python plus Docker Compose.
- **`ai-brain init`** writes `~/.config/ai-brain/machine.toml` from a template, by asking. The file is local and never
  in a repo:
  ```toml
  [machine]
  role = "work"                 # work | personal
  allow_upload = false          # machine-wide lock; false on the work machine
  url = "http://127.0.0.1:8090"
  [[brain]]
  slug = "work"
  policy = "local-only"         # local-only | backup | publish
  roots = ["~/develop"]         # what brain-map may read
  repos = ["<repo-a>", "<repo-b>"]   # the real names live only in this local file
  ```
- **`ai-brain up | down | status | upgrade`** runs the compose stack (RSC Brain at the pinned release, ParadeDB,
  Ollama with `nomic-embed-text`) on localhost only, after checking the launcher's SHA-256 against the pinned value.
- **`ai-brain activate | deactivate`** registers or unregisters, for Claude Code:
  - the MCP server and RSC Brain's hooks;
  - the overdue-consolidation check;
  - the weekly job.

  The token goes to the vault when present, else to a `0600` file. AI-HQ's `brain` module calls these two commands.
- **`ai-brain backup <brain>`** takes RSC Brain's encrypted copy and pushes the ciphertext to the private repo set in
  `[backup] remote`. **`ai-brain publish <brain>`** exports approved wiki pages as markdown to the repo set in
  `[[brain]] publish_remote`.
- **Both refuse** when the brain's policy does not allow that action, or when `allow_upload = false`. Every refusal
  says which lock refused. `local-only` brains get local encrypted copies only.
- **The guard** (`guards` module) blocks `git push` from the backup and export working folders when the policy
  forbids it, as a second line of defence.

### D3 · What goes where (taxonomy, in the standard)

| Knowledge | Canonical place | In the brain |
|---|---|---|
| Behaviour today | `openspec/specs/` | a link plus why it is so |
| Decision | `docs/adr/` | a link, alternatives explored, context |
| Work state, history | issue, PR, release | a link |
| Research, attempts, failures, domain and client context, "why", lessons | **brain** | the page itself |

A brain page that restates a spec, ADR or issue is a lint finding of the consolidation. A lesson recorded twice goes
through ASP-071: it becomes an ai-specs change, and the brain links to the result.

### D4 · Write path: journal free, wiki curated, consolidation logged
- **Journal.** Agents save to the journal freely, with a topic so that a later save revises instead of repeating.
  Secrets are redacted by RSC Brain.
- **Wiki.** It changes only through proposals that the owner decides in the web, bound to a fingerprint. In the pilot
  no key may decide; only a person can.
- **Consolidation.** The one automatic exception is D10's journal-level forgetting and merging, which is logged and
  can be undone.

### D5 · Session protocol
- **Session start:** a hook adds the brain context of the repo's git remote. Repos without a linked brain get
  nothing, so a repo outside the machine's brains never gets anything injected.
- **During work:** search before deciding, then save decisions, attempts, facts and lessons.
- **Stop:** a hook asks once for `mem_session_summary` when the session saved work without a summary.

All of this is RSC Brain's own hooks and MCP protocol. AI-HQ only installs them.

### D6 · AI-HQ integration
- **Module `brain`** delegates to `ai-brain` (`activate`/`deactivate`, and `up` as a stack service), cloned next to
  ai-hq like ai-skills (`[hq] brain_lib_remote`). It is optional and off in every profile, so a machine adds it explicitly
  (`--modules coding,brain` on the work machine, `full,brain` on the personal one):
  - `install.sh` registers `claude mcp add --transport http rsc-brain <url>/mcp --scope user` and merges the two hooks
    into `~/.claude/settings.json`, through `install_hooks.py`, marked as ours;
  - removing the module removes them;
  - the token is kept by the vault (`hq secrets track-env RSC_BRAIN_TOKEN`).
- **Registry:**
  - `[hq] brain_url`;
  - stack `brain`: a `compose` service running RSC Brain's launcher, plus Ollama;
  - `[projects.<id>] brain = "<slug>"`.
- **Scheduler:** a user-level weekly job (systemd user timer, or cron under WSL) runs `brain-consolidate` headless.
  It has a fixed, read-and-propose-only tool allowlist; see D11.
- **Machines without the vault** (the work machine): the token is kept in a `0600` file under `~/.config/rsc-brain/`.
  It is never stored in a repo.

### D7 · Flow hooks (skills)
Every hook is a no-op when no brain is connected.

| Skill | What it adds |
|---|---|
| `/hq-grill`, `/hq-spec` | `mem_search` over the repo's brain (and `personal` on the personal machine) before writing. Results feed Prior art, Must respect and Change impact, with links. When the area has no coverage, they run `brain-map` on it first (D9). |
| `/hq-tickets` | Each ticket gets the pages the builder must read (links). |
| `/hq-factory` | Per ticket: `mem_save` for decisions, failed attempts with their error, and lessons (topic `<repo>/<area>`). At the end: `mem_session_summary`. |
| `/hq-triage` | New issues link related brain pages. |
| `/hq-retro` | Runs `brain-consolidate` (D10) and shows the owner what it proposed and what it forgot. |

### D8 · Pilot and exit criteria
The pilot runs for two weeks on each machine: the work machine with brain `work`, and the personal machine with
`personal` and `langbrain`. It measures:
- the share of sessions that start with context the agent used (from the session summaries);
- the owner's curation minutes per week;
- mistakes repeated after being recorded;
- search usefulness (top-3 contains the needed page) on 20 sampled questions.

**Adopt** when context is used in ≥ 60 % of sessions, curation takes ≤ 30 min a week, and there are no repeated
recorded mistakes. Otherwise **retire**: export to markdown into `hq-workspace/brain-export/`, then remove the module.

**Where each pilot record lives.** The personal machine's record is `PILOT.md` in its AI-HQ job. The work machine's
record stays **local** (`~/.local/share/rsc-brain/pilot.md`), because the personal workspace is pushed to GitHub and
company knowledge must never reach it.

### D9 · Skill `brain-map`: map every repo, incrementally, and fill gaps on demand
`brain-map` lives in ai-skills (neutral), so it works on the work machine without AI-HQ. It reads only; it never
writes into a repo.
1. **Scope.** The repos under the machine's roots (`~/develop` on the work machine, `~/personal-assistant` on the
   personal one; set in the brain's local config). Repos without a linked brain are skipped.
2. **Per repo,** with parallel `repo-scout` subagents in a fresh context:
   - the repo's own rules (`AGENTS.md`/`CLAUDE.md`), specs, ADRs, contracts, docs, manifests and structure;
   - **Output:** pages under `<repo>/…` (overview, architecture, contracts and interfaces, conventions, commands and
     gates, open risks), each citing its source paths and the commit read.
3. **Across repos:** typed links for shared databases, contracts, provider/consumer pairs and shared conventions
   (`depends on`, `part of`, `contradicts`), plus one index page per repo.
4. **Write path:** pages go as **proposals** for the owner. The run's summary goes to the journal under
   `<repo>/mapping`, with the commit SHA mapped.
5. **Incremental:** the next run reads the last mapped SHA from the journal and maps only `git diff <sha>..HEAD`. A
   repo without changes is skipped.
6. **Gap-driven:** `/hq-grill`, `/hq-spec` (and, in any repo, `brain-map <path-or-area>`) check whether the area has
   pages. When it does not, they map that area first. The brain fills itself where work is about to happen.

### D10 · Skill `brain-consolidate`: the "dream"
It also lives in ai-skills (neutral). Each run:
1. **Health:** `brain_health` for orphans, broken links, contradictions, stale pages, near-duplicates, overlong
   pages and restated canonical content.
2. **Synthesis:** clusters of journal entries on one topic become a proposed page or an update. Near-duplicates
   become one proposal that `supersedes` the others. Contradictions become a proposal that resolves them, or a
   question for the owner.
3. **Forgetting**, by a decay score per journal entry. The score falls with age and rises with use (reads and search
   hits in the brain's trail), inbound links and references from pages.
   - **Automatic** (logged, undoable): an entry below the threshold, older than 30 days and not cited by any page is
     forgotten with `mem_forget`.
   - **Proposed, never automatic:** a page goes to the owner as an "archive" proposal.
   - **Never forgotten:** decisions, corrections and anything a person approved.
4. **Report:** what was proposed, merged and forgotten goes to the journal under `meta/consolidation`, with the run
   date. The next session-start check reads it.

### D11 · Weekly run and the overdue check
- **Scheduled:** the `brain` module installs a weekly user job:

  ```
  claude -p "/brain-consolidate" --allowedTools "mcp__rsc-brain__*" Read Grep Glob
  ```

  It runs with that allowlist only: no shell writes, no edits to files outside the brain.
- **Overdue check:** at session start a small hook reads `meta/consolidation`. When the last run is more than 7 days
  old (the machine was off), it asks the agent to offer `/brain-consolidate` once. RSC Brain's own daily-cleanup
  reminder stays on too.
- **Failure:** a failed scheduled run leaves a journal entry. The next session start reports it; nothing is retried
  silently.

### Answers given at approval
- **Company memory:** stored only on the work machine and never uploaded. Brain `work` is `local-only` and the work
  machine has `allow_upload = false` (D12).
- **Ollama:** on from the first install; meaning search is part of the pilot.
- **Vector store:** `pgvector` in the same PostgreSQL (the ParadeDB image), not a separate vector database (D2).

## Compatibility and migration

- **Nothing existing moves:**
  - `hq-workspace/memory/*.md` stays readable;
  - from the pilot on, new lessons go to the `personal` brain;
  - `lessons.py repeated` reads the file only.
- **Existing files can be imported** with RSC Brain's folder import if the owner wants. This is optional, and their
  content is reviewed as proposals.
- **Requirements:** RSC Brain needs Docker with Compose v2, PostgreSQL 17 (bundled), Node ≥ 25 (inside its image)
  and git. `prereqs.py` adds Docker for the `brain` module.

## Security and operations

- **Self-hosted:**
  - the web and MCP listen only on localhost in the pilot;
  - tokens live in the vault, never in repos;
  - the installation key goes to the owner's password manager;
  - encrypted daily copies are on.
- **Boundaries:**
  - one installation per machine; company knowledge only in the work machine's `work` brain; nothing syncs;
  - a hook in a repo without a linked brain injects nothing;
  - `brain-map` reads only the configured roots and never reads `.env` files or secrets: the guards block them, and
    RSC Brain redacts what slips through.
- **Prompt injection.** Brain pages are data. Agents treat them like any other untrusted input; ai-skills' reviewers
  already state this rule.
- **Supply chain.** The launcher is checked against its release SHA-256. The version is pinned in the registry, and
  upgrades go through a change.

## Test strategy

- **ai-hq:**
  - module and installer tests: register and unregister the MCP server and the two hooks in a temporary HOME;
  - prereqs for Docker;
  - registry fields;
  - skill tests that check each hook says it is a no-op without a brain.
- **ai-specs:** a standard test that the memory section holds the taxonomy table.
- **ai-skills:**
  - `brain-map` and `brain-consolidate` pass the structure and neutrality lint;
  - unit tests of the decay score and the forgetting rule (`scripts/brain_decay.py`, stdlib): decisions and approved
    pages are never selected; entries cited by pages are never selected.
- **Behavioural check:** during the pilot, one real change on LangBrain from `/hq-grill` to merge, where the brain
  supplies prior art in `/hq-spec`, and a new session on another day recovers the attempts saved by `/hq-factory`.

## Change impact

| Changed | Used by today | Breaks? | Mitigation / rollback |
|---|---|---|---|
| Standard memory section (taxonomy, brain links) | every adopting repo's agents | no (adds a place, removes none) | revert the section |
| AI-HQ module `brain`, stack, registry fields | `hq up` on machines that choose it | no (opt-in on each machine; off in every profile by default) | `--modules` without `brain` uninstalls it |
| Skill hooks (grill, spec, tickets, factory, triage, retro) | the owner's flow | no (no-op without a brain) | revert the skill text |
| New lessons → `personal` brain | `/hq-retro` | no (file stays) | keep writing the file |

## Rollback

1. Export every brain to markdown.
2. Run `hq up --modules <profile without brain>`, which removes the MCP server and the hooks.
3. Run `hq down brain`, then uninstall RSC Brain with its launcher.
4. Revert the merge commits.

No repo data depends on the brain, because canonical knowledge never lived only there.

## Implementation notes

Deviations found while building, recorded here so the design matches what ships:

- **Hooks are a Python port.** RSC Brain's own Claude Code hooks are its Node CLI (`rsc-brain hook session-start|stop`),
  which needs Node ≥ 25 on the host. The machines run Node 22, so `ai-brain hook session-start|stop` is a stdlib Python
  port with the same contract: JSON on stdin; `POST /v1/resolve` with the repo's git remote,
  `GET /v1/brains/<slug>/context`, `GET /v1/me/sessions`; it fails open; the token comes from `RSC_BRAIN_TOKEN` or else
  `~/.config/rsc-brain/token` (`0600`). The session-start hook also carries the overdue-consolidation note (D11).
- **Ollama runs as a container** in `ai-brain`'s compose project (localhost only), next to ParadeDB, and RSC Brain
  reaches it through `compose.override.yaml` in its install folder. Nothing is installed on the host.
- **A copy holds the whole installation.** RSC Brain's `backup` is an encrypted file of every brain on the machine, so
  `ai-brain backup <brain>` is allowed only when every brain on the machine allows `backup` and the machine allows
  upload: the strictest policy wins, and the refusal names each lock (D12, ASP-110).
- **Where the tests live.** The token scope, the weekly job and the overdue check are code of `ai-brain`, so
  `TokenScopeTest`, `ScheduleTest` and `OverdueTest` are in `ai-brain`'s `tests/test_ai_brain.py`. ai-hq keeps
  `InstallTest`, `RegistryTest` and `SkillHooksTest` in `tests/test_brain_module.py`. Task 3.1 and the proofs of
  ASP-102 and ASP-108 point there.
- **Two credentials, neither stored by the installer.** The MCP server authenticates with `claude mcp login rsc-brain`
  (OAuth, kept by Claude Code). The hooks use a read+write token without wiki-write permission, saved by the person to
  `~/.config/rsc-brain/token` or the vault. `ai-brain activate` prints both steps and never asks for a token.
- **Workspace ADR number.** The workspace decision is ADR-019, because ADR-018 was already taken.
- **Kit version.** The memory section ships in kit 0.2.2 (ADR-0004).
- **The weekly run is fenced in, not only pre-approved** (security review). `--allowedTools` only pre-approves tools,
  so the job also passes `--disallowedTools Bash Edit Write NotebookEdit WebFetch WebSearch`, `--strict-mcp-config`
  with a config holding only `rsc-brain`, and `--permission-mode dontAsk`, and runs from an empty working folder of its
  own, so global permission rules and other MCP servers cannot widen it and Read cannot reach the home folder by default.
- **No host ports for the database or Ollama** (security review). ParadeDB and Ollama sit on an internal Docker network
  `ai-brain`; RSC Brain's app joins it through `compose.override.yaml` and reaches `paradedb:5432` and `ollama:11434`
  by name. Only the web stays on `127.0.0.1:8090`. The launcher's first-install database check runs in a throwaway
  container; while the launcher runs, a small `docker` wrapper first on its PATH adds `--network ai-brain` to exactly
  that call (the launcher file is unchanged and still SHA-256-checked).
- **Undeclared brains block a backup.** The installation's real brain list is read from its database; a brain missing
  from `machine.toml` counts as `local-only`, and an unreadable list refuses.
- **OAuth connections cannot decide.** Like tokens, an OAuth connection needs a curator-granted wiki-write row to decide
  or write the wiki; the activation text tells the person to consent read + write and never grant it.
