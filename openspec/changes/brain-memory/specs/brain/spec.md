## Purpose

Gives every agent a shared, searchable and linked working memory, organised by topic and kept private or shared on purpose.

## ADDED Requirements

### Requirement: ASP-099 — One local memory per machine, nothing leaves it
Each machine SHALL run its own RSC Brain installation listening on localhost only, holding only the brains of the work
done on that machine (the work machine: `work`; the personal machine: `personal`, `method`, `langbrain`, `clothy`);
no brain content SHALL be synchronised, copied or sent to another machine or to a cloud service.

#### Scenario: No company knowledge on the personal machine
- **GIVEN** the personal machine's installation
- **WHEN** its brains are listed and its search is asked about a company repo
- **THEN** no `work` brain exists and the search returns nothing about company repos
- **Proof:** the pilot record of the personal machine lists its brains and the empty search (human gate)

### Requirement: ASP-100 — Topics inside a brain, brains as sharing boundaries
Working knowledge SHALL live in RSC Brain with topics as `<area>/<topic>` namespaces inside a brain, each topic with an
index page; separate brains SHALL exist only where the set of readers differs (`personal`, `method`, one per product),
and every registered repo with a brain SHALL name it in the registry field `brain`.

#### Scenario: A repo resolves its brain
- **GIVEN** LangBrain registered with `brain = "langbrain"` and linked to that brain by its git remote
- **WHEN** a Claude Code session starts in its checkout
- **THEN** the session receives the `langbrain` brain's context and no other brain's
- **Proof:** the pilot's first session log in the job shows the injected context naming `langbrain` (behavioural check)

### Requirement: ASP-101 — Hybrid retrieval stays on the machine
Brain search SHALL combine word ranking (BM25, `pg_search`) and meaning ranking (`pgvector`) by rank fusion in the same
PostgreSQL (the ParadeDB image), with embeddings computed by a local Ollama model enabled from the first install; no brain text SHALL be sent to a cloud provider, and without the extensions search SHALL still
work by words.

#### Scenario: Meaning search without a cloud key
- **GIVEN** the `brain` stack running with Ollama and no cloud embedding key in its environment
- **WHEN** an agent searches for a paraphrase of a page title
- **THEN** the page is in the top three results and the brain's log reports the meaning provider as Ollama
- **Proof:** `hq status brain` lists Ollama and the pilot's 20-question sample records top-3 hits (behavioural check)

### Requirement: ASP-102 — Journal free, wiki curated by a person
Agents SHALL write only to the journal and to proposals; during the pilot no key SHALL be allowed to decide proposals,
so every wiki change is decided by the owner in the web against the proposal's fingerprint.

#### Scenario: Agent key cannot decide
- **GIVEN** the agent token installed by the `brain` module
- **WHEN** it calls `brain_decide` on a proposal
- **THEN** the call is refused for lack of permission and the wiki is unchanged
- **Proof:** `python3 -m unittest tests.test_ai_brain.TokenScopeTest` in ai-brain passes (checks the install requests a contributor key only)

### Requirement: ASP-103 — AI-HQ module brain
AI-HQ SHALL offer an optional module `brain` that registers the RSC Brain MCP server, its session-start and stop hooks
and the weekly consolidation job, keeps the token in the vault (or a `0600` file on a machine without the vault), and is
removed completely when the module is not chosen; no profile SHALL include it by default, and any profile MAY add it
(`coding,brain`, `full,brain`).

#### Scenario: Install and remove in an isolated home
- **GIVEN** a temporary HOME and `[hq] brain_url` set in the registry
- **WHEN** `install.sh --modules coding,brain` runs and then `install.sh --modules coding`
- **THEN** the first registers the MCP server, both hooks and the weekly job, and the second removes them and leaves the guards
- **Proof:** `python3 -m unittest tests.test_brain_module.InstallTest` in ai-hq passes

### Requirement: ASP-104 — The flow reads before deciding and writes what it learns
When a brain is connected, `/hq-grill` and `/hq-spec` SHALL search the repo's brain and `personal` before writing and
cite the pages used; `/hq-factory` SHALL save decisions, failed attempts and lessons per ticket and close with a session
summary; `/hq-retro` SHALL run the consolidation (health, contradictions, orphans, stale and restated pages) and compile
proposals for the owner; each of these steps SHALL be a no-op when no brain is connected.

#### Scenario: No brain connected
- **GIVEN** a machine without the `brain` module
- **WHEN** `/hq-spec` runs
- **THEN** it writes the change exactly as before and says no brain was consulted
- **Proof:** `python3 -m unittest tests.test_brain_module.SkillHooksTest` in ai-hq passes

### Requirement: ASP-105 — Time-boxed pilot with exit criteria
The brain SHALL be piloted for two weeks with the brains `personal` and `langbrain`, measuring context use per session,
curation minutes per week, repeated recorded mistakes and top-3 search usefulness; it SHALL be adopted only when context
is used in at least 60 % of sessions, curation takes at most 30 minutes a week and no recorded mistake repeats, and
otherwise retired after exporting every brain to markdown.

#### Scenario: Pilot review
- **GIVEN** two weeks of pilot sessions
- **WHEN** `/hq-retro` closes the pilot
- **THEN** the job's `PILOT.md` holds the four measures and the adopt or retire decision with its evidence
- **Proof:** `hq-workspace/jobs/<brain-memory job>/PILOT.md` exists with the four measures and the owner's decision (human gate)

### Requirement: ASP-106 — brain-map maps every repo of the machine, read-only and incrementally
The ai-skills skill `brain-map` SHALL map every repo under the machine's configured roots that is linked to a brain,
reading each repo's own rules, specs, ADRs, contracts, docs and structure with read-only subagents, and SHALL propose
pages per repo (overview, architecture, contracts, conventions, commands and gates, risks) and typed links between repos,
each page citing its source paths and the mapped commit; it SHALL record the mapped commit per repo in the journal, map
only what changed since that commit on the next run, and never write into a mapped repo.

#### Scenario: Second run maps only the change
- **GIVEN** a repo mapped at commit A and two files changed in commit B
- **WHEN** `brain-map` runs again
- **THEN** it reads only the paths of `git diff A..B`, proposes updates only for the pages citing them, and records B
- **Proof:** `python3 -m unittest tests.test_brain_tools.MapScopeTest` in ai-skills passes (`scripts/brain_map_scope.py`, stdlib)

#### Scenario: Gap at the start of new work
- **GIVEN** `/hq-spec` about an area of a repo with no brain pages
- **WHEN** it searches the brain first
- **THEN** it runs `brain-map` on that area before writing and cites the new pages
- **Proof:** `python3 -m unittest tests.test_brain_module.SkillHooksTest` in ai-hq passes (the skill text names the gap rule)

### Requirement: ASP-107 — brain-consolidate synthesises and forgets with a decay rule
The ai-skills skill `brain-consolidate` SHALL run the brain's health checks, merge near-duplicates and synthesise topic
clusters into proposals, resolve or flag contradictions, and forget journal entries whose decay score (age against use,
inbound links and citations) is below the threshold, older than 30 days and cited by no page; it SHALL never forget a
decision, a correction or anything a person approved, SHALL only propose (never apply) archiving a page, and SHALL write
what it proposed, merged and forgot to the journal under `meta/consolidation`.

#### Scenario: What may be forgotten
- **GIVEN** journal entries: an old unused fact, an old unused decision, an old fact cited by a page, a recent fact
- **WHEN** the decay rule selects what to forget
- **THEN** only the old unused fact is selected
- **Proof:** `python3 -m unittest tests.test_brain_tools.DecayTest` in ai-skills passes (`scripts/brain_decay.py`, stdlib)

### Requirement: ASP-108 — Weekly consolidation, or as soon as it is overdue
The `brain` module SHALL install a weekly job that runs `brain-consolidate` headless with only the brain's MCP tools and
read-only file tools allowed, and a session-start check that, when the last `meta/consolidation` run is older than 7
days or failed, asks once to run it; a failed run SHALL be reported at the next session start and never retried
silently.

#### Scenario: Machine was off for two weeks
- **GIVEN** a last consolidation 15 days ago
- **WHEN** a session starts
- **THEN** the agent is asked once to offer `/brain-consolidate`
- **Proof:** `python3 -m unittest tests.test_ai_brain.OverdueTest` in ai-brain passes

#### Scenario: Scheduled run's permissions
- **GIVEN** the installed weekly job
- **WHEN** its command line is read
- **THEN** it runs `claude -p "/brain-consolidate" --allowedTools "mcp__rsc-brain__*" Read Grep Glob --disallowedTools Bash Edit Write NotebookEdit WebFetch WebSearch --strict-mcp-config --mcp-config <a file with only rsc-brain> --permission-mode dontAsk` from an empty working folder of its own
- **Proof:** `python3 -m unittest tests.test_ai_brain.ScheduleTest` in ai-brain passes

### Requirement: ASP-109 — ai-brain manages each machine's memory
A standalone repo `ai-brain` SHALL install, run and upgrade the machine's RSC Brain (pinned release verified by SHA-256),
ParadeDB and Ollama on localhost only, keep the machine's configuration in `~/.config/ai-brain/machine.toml` outside any
repo, and activate or deactivate the brain for the agents (MCP server, hooks, overdue check, weekly consolidation).

#### Scenario: A tampered launcher is refused
- **GIVEN** a downloaded launcher whose SHA-256 differs from the pinned value
- **WHEN** `ai-brain up` runs
- **THEN** it exits 1 before starting anything and names both hashes
- **Proof:** `python3 -m unittest tests.test_ai_brain.InstallTest` in ai-brain passes

#### Scenario: Config never lands in a repo
- **GIVEN** `ai-brain init` on a machine
- **WHEN** it writes the configuration
- **THEN** the file is `~/.config/ai-brain/machine.toml` with mode 0600 and the repo's working tree is unchanged
- **Proof:** `python3 -m unittest tests.test_ai_brain.ConfigTest` in ai-brain passes

### Requirement: ASP-110 — Sharing policy per brain with a machine-wide lock
Every brain SHALL declare a policy `local-only`, `backup` or `publish`; `ai-brain backup` SHALL send only RSC Brain's
encrypted copy to the configured private remote and `ai-brain publish` only approved wiki pages as markdown; both SHALL
refuse, naming the lock, when the brain's policy does not allow the action or the machine has `allow_upload = false`, and
no raw database dump SHALL ever be committed.

#### Scenario: The company brain cannot leave the machine
- **GIVEN** brain `work` with policy `local-only` on a machine with `allow_upload = false`
- **WHEN** `ai-brain backup work` or `ai-brain publish work` runs
- **THEN** each exits 1 naming both locks and nothing is pushed or written outside the machine's local copy folder
- **Proof:** `python3 -m unittest tests.test_ai_brain.PolicyTest` in ai-brain passes

#### Scenario: A personal backup is ciphertext only
- **GIVEN** brain `personal` with policy `backup` and an upload-allowed machine
- **WHEN** `ai-brain backup personal` prepares the push
- **THEN** the files staged are only encrypted copy files and a manifest of names and dates, never `.sql`, `.json` or markdown content
- **Proof:** `python3 -m unittest tests.test_ai_brain.PolicyTest.test_backup_stages_ciphertext_only` in ai-brain passes
