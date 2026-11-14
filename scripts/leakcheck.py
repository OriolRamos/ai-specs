"""Local leak check (ASP-090): internal names listed in a file that never leaves the machine. Stdlib only.

The terms file is `~/.config/ai-specs/forbidden-terms.txt` (or `$AI_SPECS_TERMS_FILE`): one term per line, `#` comments.
Matches are case-insensitive and whole-word (a term is not matched inside a longer word). Results name files only;
the terms themselves are never printed, so they cannot leak through logs either.
"""
from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path

DEFAULT_FILE = Path("~/.config/ai-specs/forbidden-terms.txt")


def terms_file() -> Path:
    return Path(os.environ.get("AI_SPECS_TERMS_FILE", "") or DEFAULT_FILE).expanduser()


def load_terms(path: Path | None = None) -> list[str]:
    path = path or terms_file()
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    return [ln.strip() for ln in lines if ln.strip() and not ln.strip().startswith("#")]


def pattern(terms: list[str]) -> re.Pattern[str] | None:
    if not terms:
        return None
    alternatives = "|".join(re.escape(t) for t in sorted(terms, key=len, reverse=True))
    return re.compile(rf"(?<![A-Za-z0-9])(?:{alternatives})(?![A-Za-z0-9])", re.IGNORECASE)


def _git(repo: Path, *args: str) -> str:
    res = subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True, check=False,
                         encoding="utf-8", errors="replace")
    if res.returncode != 0:
        raise RuntimeError(f"git {' '.join(args[:2])}: {res.stderr.strip()}")
    return res.stdout


def _files(repo: Path) -> list[str]:
    """Tracked files of a git work tree; every file outside `.git` when the folder is not one (a fresh kit target)."""
    inside = subprocess.run(["git", "-C", str(repo), "rev-parse", "--is-inside-work-tree"], capture_output=True,
                            text=True, check=False)
    if inside.returncode == 0 and inside.stdout.strip() == "true":
        return [rel for rel in _git(repo, "ls-files", "-z").split("\0") if rel]
    return sorted(p.relative_to(repo).as_posix() for p in repo.rglob("*")
                  if p.is_file() and ".git" not in p.relative_to(repo).parts)


def scan(repo: Path, terms: list[str], rev_range: str | None = None) -> list[str]:
    """Files whose tracked content (or whose lines added in `rev_range`) contain a term. Sorted, no duplicates."""
    rx = pattern(terms)
    if rx is None:
        return []
    hits: set[str] = set()
    if rev_range:
        current = ""
        for line in _git(repo, "diff", "--no-color", "--unified=0", rev_range).splitlines():
            if line.startswith("+++ "):
                current = line[6:] if line.startswith("+++ b/") else ""
            elif line.startswith("+") and not line.startswith("+++") and current and rx.search(line):
                hits.add(current)
        return sorted(hits)
    for rel in _files(repo):
        path = repo / rel
        try:
            data = path.read_bytes()
        except OSError:
            continue
        if b"\0" in data[:4096]:  # binary
            continue
        if rx.search(data.decode("utf-8", errors="replace")) or rx.search(rel):
            hits.add(rel)
    return sorted(hits)
