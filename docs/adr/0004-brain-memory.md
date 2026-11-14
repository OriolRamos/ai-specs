# ADR-0004 · Brain memory: local working memory per machine (kit 0.2.2)

- **Date:** 2026-11-14 · **Status:** accepted
- **Change:** `openspec/changes/brain-memory`

## Context
Specs, ADRs, issues and `.agents/memory/` keep behaviour, decisions, state and regenerable context well. Research,
attempts, failures, domain context and the reasons behind a design were lost when a session ended, or scattered
across private notes with no search and no links.

## Decision
- The standard's memory section (13) adds an optional **brain**: a self-hosted, searchable store of linked pages by
  topic, with a taxonomy table saying what goes in it and what stays canonical elsewhere.
- **The brain links, it does not define (ASP-073):** a brain page links to a spec, ADR or issue instead of restating
  it, and the consolidation reports restated content.
- **One memory per machine:** one installation per machine on localhost; nothing syncs, and nothing leaves the
  machine except through `ai-brain`'s sharing policies.

## Consequences
No lint rule changes, so adopting repos need nothing beyond re-running `init` after the `v0.2.2` tag exists. The
brain stays optional: a repo without one loses nothing, because canonical knowledge never lives only there.
