#!/usr/bin/env bash
# End-to-end check of the kit with the real OpenSpec CLI, in a throwaway folder (CI and before a release).
# init → new change → scaffold → fill → lint → validate --strict → instructions (config parsed, rules listed)
# → archive (the Proof line reaches the living spec).
# Uses $OPENSPEC if set, else `openspec` on PATH, else the pinned version through npx.
set -euo pipefail

KIT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VERSION="$(sed -n 's/^OPENSPEC_VERSION = "\(.*\)"/\1/p' "$KIT/scripts/ai_specs.py")"
if [ -n "${OPENSPEC:-}" ]; then read -r -a OS <<<"$OPENSPEC"
elif command -v openspec >/dev/null 2>&1; then OS=(openspec)
else OS=(npx -y "@fission-ai/openspec@$VERSION"); fi
AI=(python3 "$KIT/scripts/ai_specs.py")
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT
cd "$WORK"
step() { printf '\n== %s\n' "$*"; }

step "init"
printf '# e2e\n' > AGENTS.md
"${AI[@]}" init . --prefix EE --owner e2e-owner --gate "true" --kit-repo e2e/ai-specs
test -f openspec/roles.yaml && test -f .github/workflows/ai-specs.yml
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

step "contract conformance (real validators; set AI_SPECS_E2E_OFFLINE=1 to skip without network)"
"${AI[@]}" contract new . greeting --kind jsonschema >/dev/null
if [ "${AI_SPECS_E2E_OFFLINE:-0}" = "1" ]; then echo "skipped (offline)"; else "${AI[@]}" contract check .; fi
"${AI[@]}" doctor . >/dev/null
echo "e2e: ok"
