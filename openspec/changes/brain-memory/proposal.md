**Size:** L

## Why

Every agent session starts from zero. The flow keeps four kinds of memory well:
- behaviour, in OpenSpec living specs and the change archive;
- decisions, in ADRs;
- work state and history, in GitHub issues and PRs (or the company's own tracker);
- regenerable repo context, in `.agents/memory/`.

Everything else is lost when a session ends: research, failed attempts, bugs already solved, domain context, the
reasons behind a design, how the repos of a machine fit together. What survives is scattered:
- `hq-workspace/memory/*.md`;
- LangBrain's local SQLite;
- Claude Code's per-machine auto-memory.

There is no search across them, no links between them, and no upkeep.

The owner wants three things:
- **a hybrid memory:** fast retrieval (word and meaning search) over documents **linked in a graph** and organised
  **by topic**;
- **a memory local to each machine and context:** on the work machine, the knowledge of the company repos; on the
  personal machine, none of it;
- **two capabilities beyond storage:**
  - a skill that **maps every repo of the machine**, synthesises it and **enriches itself** when new work starts in an
    area it does not know yet;
  - a skill that runs **every week, or as soon as it notices it is overdue**, to consolidate what the brain holds and
    **forget what is irrelevant**, the way a human brain does in sleep.

## What Changes

- **A memory layer, run by RSC Brain** (MIT, self-hosted, PostgreSQL, MCP), **installed locally on each machine**.
  There is no sync and no remote: each installation listens on localhost and holds only that machine's brains.
  - **Work machine:** brain `work`.
  - **Personal machine:** brains `personal`, `method`, `langbrain`, `clothy`.
- **Topology.**
  - Topics are **namespaces inside a brain** (`<repo-or-area>/<topic>`), each with an index page, so the graph stays
    connected across topics. RSC Brain links do not cross brains.
  - Brains are created only where readers differ. Repos are linked to their brain by git remote.
- **Hybrid retrieval in one database.** RSC Brain's PostgreSQL runs on the **ParadeDB** image, which ships both
  `pg_search` (BM25) and `pgvector`. Embeddings come from a **local Ollama** `nomic-embed-text` (on from day one),
  fused by rank. Text, vectors, graph and permissions live in one database with one backup; nothing goes to a cloud
  service.
- **A new repo, `ai-brain`, manages all of it on each machine** (standalone, like ai-skills; AI-HQ's `brain` module
  calls it). It does five things:
  - **Installs and upgrades** RSC Brain (pinned release, SHA-256 checked), ParadeDB and Ollama, on localhost.
  - **Keeps a local machine config** (`~/.config/ai-brain/machine.toml`, never in a repo): the machine's brains, their
    roots and repos, and a machine-wide `allow_upload`.
  - **Activates it for the agents:** the MCP server, the hooks and the weekly consolidation.
  - **Applies a sharing policy per brain:**
    - `local-only`: nothing leaves the machine, not even backups;
    - `backup`: an **encrypted** snapshot to a private GitHub repo;
    - `publish`: **approved wiki pages only**, as markdown, to a repo the owner names.
  - **Refuses any upload** when the brain's policy or the machine's `allow_upload` forbids it.
- **Write path.** Agents write freely to the **journal**. The **wiki** changes through proposals. In the pilot the
  owner decides every wiki proposal, except the low-risk consolidation steps on the journal, which run automatically
  and are logged.
- **Skill `brain-map`** (ai-skills, neutral). It maps every repo under the machine's configured roots with parallel
  read-only scouts. It reads each repo's own rules, specs, ADRs, contracts, docs and structure, and compiles pages:
  one overview per repo, its architecture, contracts, conventions, and the cross-repo relations as typed links.
  - **Incremental:** it remembers the last mapped commit per repo and re-reads only what changed.
  - **Gap-driven:** when work starts in an area the brain does not cover, it maps that area first.
- **Skill `brain-consolidate`, the "dream"** (ai-skills, neutral). It merges duplicates, synthesises clusters of
  journal entries into proposed pages, resolves or flags contradictions, links orphans, supersedes stale pages, and
  **forgets** with a decay rule. Decisions and pages the owner approved are never forgotten automatically.
  - **Triggers:** a weekly scheduled run, plus a check at session start that asks to run it when the last one is
    older than 7 days.
- **Taxonomy rule in the standard.** Specs, ADRs and issues stay canonical; the brain links to them and never
  restates them. A lesson that becomes a norm leaves the brain through a change (ASP-071), or through the company's
  own process in company repos.
- **AI-HQ module `brain`.** It registers the MCP server and RSC Brain's session hooks, installs the scheduler for the
  weekly consolidation and keeps the token in the vault (or a local file on a machine without the vault).
  - **Optional:** off in every profile by default; a machine adds it explicitly, e.g. `--modules coding,brain`.
- **Flow hooks:**
  - `/hq-grill` and `/hq-spec` search first and trigger `brain-map` on gaps;
  - `/hq-factory` saves attempts and lessons;
  - `/hq-triage` links pages;
  - `/hq-retro` runs `brain-consolidate`.
- **A two-week pilot per machine with exit criteria.** Adopt or retire, decided with numbers. Export to markdown means
  retiring loses nothing.
- **Excludes:**
  - building our own vector database or RAG service;
  - syncing or copying memory between machines;
  - cloud embedding providers;
  - LangBrain's `ProjectMemoryStore` migration (after the pilot);
  - writing into company repos.

## Not to add

- No memory leaves the machine except through `ai-brain`'s policies. Policy `backup` sends ciphertext only; `publish`
  sends approved wiki markdown only. There is no remote brain, no live sync, no cloud embeddings and no
  `RSC_BRAIN_OPENAI_KEY`.
- No upload of any kind for a `local-only` brain or from a machine with `allow_upload = false`: the company brain
  `work` is both.
- No raw database dump in git: git history never forgets, and forgetting is part of the brain.
- No company knowledge on the personal machine, and no personal knowledge in the work machine's brain.
- No agent decides wiki proposals in the pilot, and no agent forgets a decision or an approved page.
- No brain page that restates a spec, an ADR or an issue: it links to it.
- `brain-map` never writes into the mapped repos; it only reads them.
- No consolidation that deletes without a log entry the owner can review and undo.

## Prior art and reuse

- **RSC Brain v0.7.0** (github.com/ericrisco/rsc-brain, MIT; same author as the vendored rsc-harness skills).
  - Journal → proposals → wiki with fingerprinted review.
  - 27 MCP tools (`mem_save`, `mem_forget`, `brain_compile_pack`, `brain_health`, `brain_propose`, …) and an HTTP API.
  - Typed links and a graph view; brains with roles.
  - Repo → brain resolution by git remote; Claude Code hooks; a built-in reminder when nobody has cleaned up.
  - Secrets redaction, encrypted copies, markdown export, folder import.
  - BM25 plus `pgvector`, with Ollama.

  Reused as is. The time-boxed pilot and checking export first cover its early-development risk.
- **Karpathy's LLM Wiki** (ingest, query, lint) is the pattern. `brain-map` is ingest, the flow hooks are query, and
  `brain-consolidate` is lint plus "dream".
- **Existing pieces reused:**
  - ai-skills' `repo-scout` subagent as the read-only mapper;
  - AI-HQ modules, the vault and the scheduler code of `vault_schedule.py` for the weekly run;
  - the hooks installer;
  - the ai-specs memory section (ASP-070/071).
- **Rejected:**
  - a hand-made vector DB over raw chunks: naive RAG, with no compiled knowledge and poor multi-hop answers;
  - one brain per topic: the graph would be cut;
  - a plain markdown wiki: no shared search, no review;
  - Microsoft GraphRAG: heavy, aimed at static corpora.
