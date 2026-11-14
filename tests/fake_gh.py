#!/usr/bin/env python3
"""A fake `gh` for tests: answers the `gh api` calls ai-specs makes from a JSON state file ($FAKE_GH_STATE).

State: {"login": "...", "issues": {"12": {"body": "...", "labels": ["state:proposed"],
        "comments": [{"user": {"login": "x"}, "body": "..."}]}}, "pulls": {"7": {"body": "Closes #12"}},
        "calls": [...]}  -- every call is appended to "calls"; mutating calls change the state.
"""
from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path


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
        if state.get("offline"):
            print("error connecting to api.github.com", file=sys.stderr)
            code = 1
        elif route == "user":
            out = {"login": state["login"]} if state.get("login") else None
            code = 0 if out else 1
        elif m := re.fullmatch(r"repos/\{owner\}/\{repo\}/issues/(\d+)", route):
            issue = state["issues"][m.group(1)]
            out = {"number": int(m.group(1)), "body": issue["body"], "labels": [{"name": n} for n in issue["labels"]]}
        elif m := re.fullmatch(r"repos/\{owner\}/\{repo\}/issues/(\d+)/comments", route):
            issue = state["issues"][m.group(1)]
            if method == "POST":
                issue["comments"].append({"user": {"login": state["login"]}, "body": fields["body"]})
                out = {}
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
