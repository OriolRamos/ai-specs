#!/usr/bin/env python3
"""A fake `gh` for tests: answers the `gh api` calls ai-specs makes from a JSON state file ($FAKE_GH_STATE).

State: {"login": "...", "issues": {"12": {"body": "...", "labels": ["state:proposed"], "state": "open",
        "comments": [{"id": 1, "user": {"login": "x"}, "body": "...", "created_at": "…", "updated_at": "…"}]}},
        "pulls": {"7": {"body": "Closes #12"}}, "repo": {"default_branch": "develop", "full_name": "o/r"},
        "runs": {"77": {"event": "issue_comment", ...}}, "branches": {"change/12-demo": "<sha>"},
        "clock": 0, "calls": [...]}
Every call is appended to "calls"; mutating calls change the state. Each write advances "clock" by one second and
stamps `created_at`/`updated_at` with it, like GitHub does. A login ending in `[bot]` posts as type `Bot`.
Unknown runs, branches and comments answer `HTTP 404` like the real API.
"""
from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

DEFAULT_REPO = {"default_branch": "develop", "full_name": "o/r", "html_url": "https://github.com/o/r"}


def stamp(state: dict) -> str:
    state["clock"] = state.get("clock", 0) + 1
    minutes, seconds = divmod(state["clock"], 60)
    return f"2026-11-16T10:{minutes:02d}:{seconds:02d}Z"


def not_found(route: str) -> int:
    print(f"gh: Not Found (HTTP 404) {route}", file=sys.stderr)
    return 1


def main(argv: list[str]) -> int:
    path = Path(os.environ["FAKE_GH_STATE"])
    state = json.loads(path.read_text(encoding="utf-8"))
    state.setdefault("calls", []).append(argv)
    out: object = None
    code = 0
    if argv[:1] != ["api"]:
        print(f"fake gh: unsupported {argv}", file=sys.stderr)
        code = 1
    else:
        route, method, fields = argv[1], "GET", {}
        rest = argv[2:]
        i = 0
        while i < len(rest):
            if rest[i] == "-X":
                method, i = rest[i + 1], i + 2
            elif rest[i] == "-f":
                key, _, value = rest[i + 1].partition("=")
                fields[key], i = value, i + 2
            else:
                i += 1
        if state.get("offline") or route in state.get("fail_routes", []):
            print("error connecting to api.github.com", file=sys.stderr)
            code = 1
        elif route == "user":
            out = {"login": state["login"]} if state.get("login") else None
            code = 0 if out else 1
        elif route == "repos/{owner}/{repo}":
            out = {**DEFAULT_REPO, **state.get("repo", {})}
        elif m := re.fullmatch(r"repos/\{owner\}/\{repo\}/actions/runs/(\d+)", route):
            run = state.get("runs", {}).get(m.group(1))
            if run is None:
                code = not_found(route)
            else:
                out = {"id": int(m.group(1)), **run}
        elif m := re.fullmatch(r"repos/\{owner\}/\{repo\}/git/ref/heads/(.+)", route):
            sha = state.get("branches", {}).get(m.group(1))
            if sha is None:
                code = not_found(route)
            else:
                out = {"ref": f"refs/heads/{m.group(1)}", "object": {"sha": sha, "type": "commit"}}
        elif m := re.fullmatch(r"repos/\{owner\}/\{repo\}/issues/comments/(\d+)", route):
            found = [c for issue in state["issues"].values() for c in issue["comments"]
                     if str(c.get("id")) == m.group(1)]
            if not found:
                code = not_found(route)
            elif method == "PATCH":
                found[0]["body"] = fields["body"]
                found[0]["updated_at"] = stamp(state)
                out = found[0]
            else:
                out = found[0]
        elif m := re.fullmatch(r"repos/\{owner\}/\{repo\}/issues/(\d+)", route):
            issue = state["issues"][m.group(1)]
            out = {"number": int(m.group(1)), "body": issue["body"], "state": issue.get("state", "open"),
                   "labels": [{"name": n} for n in issue["labels"]]}
        elif m := re.fullmatch(r"repos/\{owner\}/\{repo\}/issues/(\d+)/comments", route):
            issue = state["issues"][m.group(1)]
            if method == "POST":
                login = state["login"]
                when = stamp(state)
                state["next_id"] = state.get("next_id", 1000) + 1
                note = {"id": state["next_id"], "body": fields["body"], "created_at": when, "updated_at": when,
                        "user": {"login": login, "type": "Bot" if login.endswith("[bot]") else "User"}}
                issue["comments"].append(note)
                out = note
            else:
                out = issue["comments"]
        elif m := re.fullmatch(r"repos/\{owner\}/\{repo\}/issues/(\d+)/labels", route):
            state["issues"][m.group(1)]["labels"].append(fields["labels[]"])
            out = []
        elif m := re.fullmatch(r"repos/\{owner\}/\{repo\}/issues/(\d+)/labels/(.+)", route):
            state["issues"][m.group(1)]["labels"].remove(m.group(2))
            out = []
        elif m := re.fullmatch(r"repos/\{owner\}/\{repo\}/pulls/(\d+)", route):
            out = state["pulls"][m.group(1)]
        else:
            print(f"fake gh: unknown route {route}", file=sys.stderr)
            code = 1
    path.write_text(json.dumps(state, indent=2), encoding="utf-8")
    if out is not None:
        print(json.dumps(out))
    return code


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
