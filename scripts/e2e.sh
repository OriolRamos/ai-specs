#!/usr/bin/env bash
# End-to-end check of the kit with the real OpenSpec CLI, in a throwaway folder (CI and before a release).
# init → new change → scaffold → fill → lint → validate --strict → instructions (config parsed, rules listed)
# → archive (the Proof line reaches the living spec) → terminal approval → approval card on a real git branch.
# Uses $OPENSPEC if set, else `openspec` on PATH, else the pinned version through npx.
set -euo pipefail

KIT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VERSION="$(sed -n 's/^OPENSPEC_VERSION = "\(.*\)"/\1/p' "$KIT/scripts/ai_specs.py")"
if [ -n "${OPENSPEC:-}" ]; then read -r -a OS <<<"$OPENSPEC"
elif command -v openspec >/dev/null 2>&1; then OS=(openspec)
else OS=(npx -y "@fission-ai/openspec@$VERSION"); fi
WORK="$(mktemp -d)"
KITCOPY="$(mktemp -d)"
trap 'rm -rf "$WORK" "$KITCOPY"' EXIT
step() { printf '\n== %s\n' "$*"; }
export GIT_AUTHOR_NAME=e2e GIT_AUTHOR_EMAIL=e2e@example.invalid GIT_COMMITTER_NAME=e2e GIT_COMMITTER_EMAIL=e2e@example.invalid

step "tagged copy of the kit (init pins CI to the commit of tag v<VERSION>)"
cp -r "$KIT/scripts" "$KIT/kit" "$KIT/VERSION" "$KITCOPY/"
git -C "$KITCOPY" init -q -b develop && git -C "$KITCOPY" add -A && git -C "$KITCOPY" commit -q -m kit
git -C "$KITCOPY" tag -a "v$(cat "$KIT/VERSION")" -m release
AI=(python3 "$KITCOPY/scripts/ai_specs.py")
cd "$WORK"

step "init"
printf '# e2e\n' > AGENTS.md
"${AI[@]}" init . --prefix EE --owner e2e-owner --gate "true" --kit-repo e2e/ai-specs
test -f openspec/roles.yaml && test -f .github/workflows/ai-specs.yml && test -f .github/workflows/ai-specs-approval.yml
grep -q "ref: $(git -C "$KITCOPY" rev-parse HEAD) # v" .github/workflows/ai-specs-approval.yml
grep -q "ai-specs:begin" AGENTS.md

step "new change + scaffold"
"${OS[@]}" new change add-greeting >/dev/null
"${AI[@]}" scaffold . add-greeting --size S --capability greeting
if "${AI[@]}" lint . add-greeting >/dev/null; then echo "lint must fail while TODOs remain" >&2; exit 1; fi

step "fill"
C=openspec/changes/add-greeting
cat > "$C/proposal.md" <<'MD'
**Size:** S

## Why
Callers need a greeting.

## What Changes
- Add `GET /greet`.
- **Excludes:** localisation.

## Not to add
- No auth and no new configuration options.
MD
cat > "$C/specs/greeting/spec.md" <<'MD'
## Purpose

Greets every caller by name so all clients show the same predictable text.

## ADDED Requirements

### Requirement: EE-001 — Greeting by name
The service SHALL return a greeting that contains the caller's name.

#### Scenario: Named greeting
- **GIVEN** a caller named Ada
- **WHEN** it calls `GET /greet?name=Ada`
- **THEN** the response is `200` with body `{"text": "Hello, Ada"}`
- **Proof:** `pytest tests/test_greet.py::test_named` passes
MD
printf '## 1. Greeting\n- [x] 1.1 Greeting endpoint — test first: `tests/test_greet.py::test_named` — proof: `pytest -q tests/test_greet.py`\n' > "$C/tasks.md"

step "lint + validate"
"${AI[@]}" lint . add-greeting
"${OS[@]}" validate add-greeting --strict

step "OpenSpec reads the kit config (no parse warning, rules reach the agent)"
out="$("${OS[@]}" instructions proposal --change add-greeting 2>&1)"
if grep -qi "could not parse" <<<"$out"; then echo "$out" >&2; exit 1; fi
grep -q "Not to add" <<<"$out"

step "digest is stable across ticks and survives archive"
D1="$("${AI[@]}" digest . add-greeting)"
"${OS[@]}" archive add-greeting --yes >/dev/null
grep -q "Proof:" openspec/specs/greeting/spec.md
"${OS[@]}" validate --all --strict >/dev/null || { echo "validate --all --strict failed after archive" >&2; exit 1; }
echo "validate --all --strict after archive: ok"
D2="$("${AI[@]}" digest . add-greeting)"
[ "$D1" = "$D2" ] || { echo "digest changed after archive: $D1 vs $D2" >&2; exit 1; }

step "approval with a fake gh (the real one needs a person in a terminal)"
BIN="$WORK/.bin"; mkdir -p "$BIN"
printf '#!/bin/sh\nexec python3 %s "$@"\n' "$KIT/tests/fake_gh.py" > "$BIN/gh"; chmod +x "$BIN/gh"
cat > "$WORK/gh.json" <<JSON
{"login": "e2e-owner", "pulls": {"3": {"body": "Closes #1"}},
 "issues": {"1": {"labels": ["type:change", "state:proposed"], "comments": [],
   "body": "<!-- ai-specs:change -->\nchange: add-greeting\n<!-- /ai-specs:change -->"}}}
JSON
export PATH="$BIN:$PATH" FAKE_GH_STATE="$WORK/gh.json"
if "${AI[@]}" check-approval . --pr 3 >/dev/null 2>&1; then echo "unapproved change passed the check" >&2; exit 1; fi
printf '%s\n' "${D2#sha256:}" | cut -c1-8 > "$WORK/typed"
env -u CLAUDECODE python3 - "$KIT" "$WORK" <<'PY'  # fake gh in a scratch folder: a test fixture, not an approval
import sys
from pathlib import Path
sys.path.insert(0, f"{sys.argv[1]}/scripts")
import approval
typed = Path(sys.argv[2], "typed").read_text().strip()
approval.approve(Path("."), 1, ask=lambda q: typed, is_tty=lambda: True, say=lambda m: None)
PY
"${AI[@]}" check-approval . --pr 3
python3 - "$WORK/gh.json" <<'PY'
import json, sys
state = json.load(open(sys.argv[1]))
state["pulls"]["4"] = {"body": "Back-merge (Refs #1)", "head": {"ref": "hotfix/1-crash"}}
json.dump(state, open(sys.argv[1], "w"))
PY
"${AI[@]}" check-approval . --pr 4 >/dev/null && echo "hotfix back-merge resolves its issue from the branch"

step "approval card: render from a real git branch, tick as the approver, gate passes; reword, gate fails"
BR=change/1-add-greeting
git init -q -b "$BR" . && git add -A && git commit -q -m "change 1"
python3 - "$WORK" "$BR" "$(git rev-parse HEAD)" <<'PY'  # card comments only: drop the terminal approval
import json, sys
work, branch, sha = sys.argv[1:]
state = json.load(open(f"{work}/gh.json"))
state.update(login="github-actions[bot]", branches={branch: sha}, runs={})
issue = state["issues"]["1"]
issue.update(comments=[], body=f"<!-- ai-specs:change -->\nchange: add-greeting\nbranch: {branch}\n<!-- /ai-specs:change -->")
json.dump(state, open(f"{work}/gh.json", "w"))
json.dump({"ref": f"refs/heads/{branch}", "repository": {"html_url": "https://github.com/e2e/repo"}},
          open(f"{work}/push.json", "w"))
PY
"${AI[@]}" card render . --event "$WORK/push.json" --src .
python3 - "$WORK" <<'PY'  # the approver ticks the box; GitHub runs the review job (run 900)
import json, sys
work = sys.argv[1]
state = json.load(open(f"{work}/gh.json"))
issue = state["issues"]["1"]
cards = [c for c in issue["comments"] if c["body"].startswith("<!-- ai-specs:approval-card ")]
assert len(cards) == 1, cards
card = cards[0]
card["body"] = card["body"].replace("- [ ] I approve", "- [x] I approve", 1)
state["runs"] = {"900": {"event": "issue_comment", "path": ".github/workflows/ai-specs-approval.yml",
                         "head_branch": "develop", "triggering_actor": {"login": "e2e-owner"},
                         "created_at": "2026-11-16T09:00:00Z"}}
json.dump(state, open(f"{work}/gh.json", "w"))
event = {"action": "edited", "repository": {"html_url": "https://github.com/e2e/repo"},
         "issue": {"number": 1, "state": "open", "body": issue["body"], "labels": [{"name": n} for n in issue["labels"]]},
         "comment": {"id": card["id"], "body": card["body"], "user": card["user"]},
         "sender": {"login": "e2e-owner", "type": "User"}}
json.dump(event, open(f"{work}/tick.json", "w"))
PY
GITHUB_RUN_ID=900 "${AI[@]}" card review . --event "$WORK/tick.json" --src .
"${AI[@]}" check-approval . --pr 3
PROPOSAL="$(ls -d openspec/changes/archive/*-add-greeting)/proposal.md"
printf '\nOne more caller wants it.\n' >> "$PROPOSAL"
git commit -q -am "reword" && python3 - "$WORK" "$BR" "$(git rev-parse HEAD)" <<'PY'
import json, sys
work, branch, sha = sys.argv[1:]
state = json.load(open(f"{work}/gh.json"))
state["branches"][branch] = sha
json.dump(state, open(f"{work}/gh.json", "w"))
PY
"${AI[@]}" card render . --event "$WORK/push.json" --src . | grep -q "state:proposed"
if "${AI[@]}" check-approval . --pr 3 >/dev/null 2>&1; then echo "a reworded scope kept its card approval" >&2; exit 1; fi
echo "card approval: recorded, checked, and dropped after a reword"

step "contract conformance (real validators; set AI_SPECS_E2E_OFFLINE=1 to skip without network)"
"${AI[@]}" contract new . greeting --kind jsonschema >/dev/null
if [ "${AI_SPECS_E2E_OFFLINE:-0}" = "1" ]; then echo "skipped (offline)"; else "${AI[@]}" contract check .; fi
"${AI[@]}" doctor . >/dev/null
echo "e2e: ok"
