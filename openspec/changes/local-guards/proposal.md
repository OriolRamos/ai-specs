**Size:** M

## Why

Two gaps came up while recording the brain-memory approval:

1. **The guard ignores the registry.** It protects `main`, `master`, `pre-production` and `production` in every repo,
   whatever the registry says. The private workspace is meant to take the agent's logs, lessons and job records
   directly (ADR-017), yet the guard blocked them. The owner's rule is that in his repos the work lands on `develop`.
2. **Nothing stops internal names from reaching a public repo.** A proposal in the public ai-specs repo named the
   company and its internal repos. The text was fixed and the branch rewritten, but no check would have caught it.

## What Changes

- **Guard driven by the registry.** In a registered repo, the guard protects exactly the registry's `protected`
  branches. In any other repo it keeps today's base list, so company and unknown repos keep the same protection.
- **Workspace on `develop`.** The private state repo works on `develop`: the agent commits and pushes there directly.
  `main` stays protected. This replaces "single `main`" in audit-fixes' ASP-014 (same change of intent, updated
  there).
- **Leak check.** A local terms file, `~/.config/ai-specs/forbidden-terms.txt` (one term per line, mode 0600, never
  in a repo), lists names that must not leave the machine.
  - `ai-specs leak-check <repo> [--range A..B]` scans tracked files, or the diff of a range, case-insensitively.
  - `ai-specs lint` runs it when the file exists.
  - The guard runs it on every `git push` from a registered repo or to a GitHub remote, in the folder the command
    really runs in (it follows `cd`), over the commits being pushed, and denies the push naming the files found. A
    company repo pushing to its own server is not checked: it legitimately holds those names. Terms are never written
    to any repo or log.
- **The guard follows `cd`.** `cd <dir> && git …` is checked in `<dir>`, not in the session's folder. That was a
  latent bug of the protected-branch check too.
- **Excludes:** history rewriting (a person's act); CI checks, which have no local file, so the check is local only.

## Not to add

- No terms list in any repo, workflow or CI secret: the list itself is internal knowledge.
- No change to the protection of repos outside the registry.
- No automatic rewrite or force push when a leak is found: the guard only denies and explains.

## Prior art and reuse

- **AI-HQ's guard** (`hooks/guard_bash.py`) already reads the registry for extra protected branches. It now uses the
  registry's list as the whole list for registered repos.
- **The approval flow** already keeps `develop` as the integration branch (ASP-030). The workspace adopts it as its
  working branch.
- **Rejected:** server-side secret scanning or push protection (GitHub feature), because it needs the list on GitHub;
  and a generic secret scanner, because company names are not secrets and no pattern catches them.

## Change impact

| Changed | Used by today | Breaks? | Mitigation / rollback |
|---|---|---|---|
| Guard protected list for registered repos | agent pushes in registered repos | no (registry already lists `develop`, `pre-production`, `production` for the flow repos) | revert the guard |
| Workspace `develop` | agent writes to the workspace, `hq up` updates | the local clone moves to `develop` | registry revert; `main` unchanged |
| Leak check in lint and on push | pushes from this machine | a push containing a listed term is denied (intended) | remove the terms file |
