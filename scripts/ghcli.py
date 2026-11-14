"""The only place ai-specs talks to GitHub: the `gh` CLI, run inside the repo so `{owner}/{repo}` resolves.

Every failure to run `gh` (missing, not logged in, no network) raises GhError, which callers turn into exit code 2.
Never into "approved".
"""
from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from typing import Any


class GhError(RuntimeError):
    """gh could not answer (missing, not authenticated, network, API error)."""


def run(args: list[str], cwd: Path) -> str:
    exe = shutil.which("gh")
    if not exe:
        raise GhError("the GitHub CLI `gh` is not installed (sudo apt-get install -y gh, then gh auth login)")
    try:
        res = subprocess.run([exe, *args], cwd=cwd, capture_output=True, text=True, timeout=60, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise GhError(f"gh {' '.join(args[:2])}: {exc}") from exc
    if res.returncode != 0:
        raise GhError(f"gh {' '.join(args[:3])}: {(res.stderr or res.stdout).strip()}")
    return res.stdout


def api(path: str, cwd: Path, method: str = "GET", fields: dict[str, str] | None = None,
        paginate: bool = False) -> Any:
    args = ["api", path]
    if method != "GET":
        args += ["-X", method]
    for key, value in (fields or {}).items():
        args += ["-f", f"{key}={value}"]
    if paginate:
        args.append("--paginate")
    out = run(args, cwd).strip()
    if not out:
        return None
    try:
        if not paginate:
            return json.loads(out)
        # --paginate prints one JSON document per page back to back ("[...][...]"): decode them one by one.
        decoder, pos, pages = json.JSONDecoder(), 0, []
        while pos < len(out):
            page, pos = decoder.raw_decode(out, pos)
            pages.append(page)
            while pos < len(out) and out[pos].isspace():
                pos += 1
        return [item for page in pages for item in (page if isinstance(page, list) else [page])]
    except json.JSONDecodeError as exc:
        raise GhError(f"gh api {path}: unexpected output") from exc


def login(cwd: Path) -> str:
    data = api("user", cwd)
    if not isinstance(data, dict) or not data.get("login"):
        raise GhError("gh is not logged in (gh auth login)")
    return str(data["login"])


def issue(cwd: Path, number: int) -> dict:
    return api(f"repos/{{owner}}/{{repo}}/issues/{number}", cwd)


def comments(cwd: Path, number: int) -> list[dict]:
    return api(f"repos/{{owner}}/{{repo}}/issues/{number}/comments", cwd, paginate=True) or []


def comment(cwd: Path, number: int, body: str) -> None:
    api(f"repos/{{owner}}/{{repo}}/issues/{number}/comments", cwd, method="POST", fields={"body": body})


def pull(cwd: Path, number: int) -> dict:
    return api(f"repos/{{owner}}/{{repo}}/pulls/{number}", cwd)


STATES = ("state:proposed", "state:approved", "state:in-progress", "state:in-review", "state:blocked")


def set_state(cwd: Path, number: int, state: str) -> None:
    """Exactly one `state:*` label afterwards (ASP-011)."""
    if state not in STATES:
        raise ValueError(state)
    current = {lab["name"] for lab in (issue(cwd, number).get("labels") or [])}
    for old in sorted(current & set(STATES) - {state}):
        api(f"repos/{{owner}}/{{repo}}/issues/{number}/labels/{old}", cwd, method="DELETE")
    if state not in current:
        api(f"repos/{{owner}}/{{repo}}/issues/{number}/labels", cwd, method="POST", fields={"labels[]": state})
