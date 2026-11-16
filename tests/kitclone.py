"""A throwaway copy of this kit as its own git repo, tagged `v<VERSION>`, for tests that run `init`.

Outside self mode `init` pins the kit checkout to the commit of tag `v<VERSION>` and refuses without it (ASP-119). The
working tree of the kit may be ahead of any tag, so tests copy it, commit it and tag the copy, then point
`ai_specs.KIT` at the copy. `install()` does that once per test process.
"""
from __future__ import annotations

import atexit
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

KIT = Path(__file__).resolve().parent.parent
_ROOT = Path(tempfile.mkdtemp(prefix="ai-specs-kit-"))
atexit.register(shutil.rmtree, _ROOT, True)
_cache: dict[bool, Path] = {}


def _git(cwd: Path, *args: str) -> str:
    env = {**os.environ, "GIT_AUTHOR_NAME": "kit", "GIT_AUTHOR_EMAIL": "kit@example.invalid",
           "GIT_COMMITTER_NAME": "kit", "GIT_COMMITTER_EMAIL": "kit@example.invalid"}
    return subprocess.run(["git", "-C", str(cwd), *args], capture_output=True, text=True, check=True,
                          env=env).stdout.strip()


def copy_kit(tagged: bool = True, fresh: bool = False) -> Path:
    """A committed copy of `scripts/`, `kit/` and `VERSION`; tagged `v<VERSION>` unless `tagged` is False."""
    if not fresh and tagged in _cache:
        return _cache[tagged]
    target = Path(tempfile.mkdtemp(prefix="kit-", dir=_ROOT))
    for name in ("scripts", "kit"):
        shutil.copytree(KIT / name, target / name, ignore=shutil.ignore_patterns("__pycache__"))
    shutil.copy2(KIT / "VERSION", target / "VERSION")
    _git(target, "init", "-q", "-b", "develop")
    _git(target, "add", "-A")
    _git(target, "commit", "-q", "-m", "kit")
    if tagged:
        version = (KIT / "VERSION").read_text(encoding="utf-8").strip()
        _git(target, "tag", "-a", f"v{version}", "-m", f"v{version}")
    if not fresh:
        _cache[tagged] = target
    return target


def install() -> Path:
    """Points `ai_specs.KIT` at the tagged copy for the rest of the test process."""
    import ai_specs  # noqa: PLC0415

    ai_specs.KIT = copy_kit()
    return ai_specs.KIT
