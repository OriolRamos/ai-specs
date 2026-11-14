"""Versioned contracts with conformance (ASP-040 … ASP-042), stdlib only; validators run pinned through npx."""
from __future__ import annotations

import json
import os
import re
import shlex
import subprocess
from pathlib import Path
from typing import Callable

AJV = "ajv-cli@5.0.0"
REDOCLY = "@redocly/cli@1.34.5"
NAME_RE = re.compile(r"^[a-z0-9][a-z0-9-]{1,63}$")
VERSION_DIR_RE = re.compile(r"^v(\d+)$")
Runner = Callable[[list[str], Path], "tuple[int, str]"]


class ContractError(RuntimeError):
    """`code` 1 = a contract is wrong, 2 = a validator could not run."""

    def __init__(self, message: str, code: int = 1) -> None:
        super().__init__(message)
        self.code = code


def npx_prefix() -> list[str]:
    """`npx -y` unless AI_SPECS_NPX names another runner (tests, offline mirrors)."""
    return shlex.split(os.environ.get("AI_SPECS_NPX", "npx -y"))


def default_runner(cmd: list[str], cwd: Path) -> tuple[int, str]:
    try:
        res = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=300, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise ContractError(f"cannot run {cmd[0]}: {exc}", 2) from exc
    return res.returncode, (res.stdout or "") + (res.stderr or "")


# ---------------------------------------------------------------- new (ASP-040)
SCHEMA = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "$id": "{name}/v1",
    "title": "{name} v1",
    "type": "object",
    "required": ["id"],
    "additionalProperties": False,
    "properties": {"id": {"type": "string", "minLength": 1}},
}
OPENAPI = """openapi: 3.1.0
info:
  title: {name}
  version: 1.0.0
  license:
    name: Proprietary
servers:
  - url: http://localhost
security: []
paths:
  /health:
    get:
      operationId: getHealth
      summary: Health check
      responses:
        "200":
          description: The service answers.
          content:
            application/json:
              schema:
                type: object
                required: [status]
                properties:
                  status:
                    type: string
"""


def new(repo: Path, name: str, kind: str) -> list[str]:
    if not NAME_RE.match(name):
        raise ContractError(f"contract name '{name}' must be kebab-case")
    if kind not in ("jsonschema", "openapi"):
        raise ContractError("kind must be jsonschema or openapi")
    folder = repo / "contracts" / name / "v1"
    if folder.exists():
        raise ContractError(f"{folder.relative_to(repo)} already exists")
    files: dict[str, str] = {
        "README.md": (f"# Contract {name} v1\n\n- **Provider:** <module>\n- **Consumers:** <modules>\n"
                      "- **Compatibility:** this version is immutable once released; breaking changes go to v2.\n"),
        "examples/valid/example.json": json.dumps({"id": "example"}, indent=2) + "\n",
    }
    if kind == "jsonschema":
        schema = json.loads(json.dumps(SCHEMA).replace("{name}", name))
        files["schema.json"] = json.dumps(schema, indent=2) + "\n"
        files["examples/invalid/missing-required.json"] = "{}\n"
    else:
        files["openapi.yaml"] = OPENAPI.format(name=name)
        files["examples/valid/example.json"] = json.dumps({"status": "ok"}, indent=2) + "\n"
    for rel, text in files.items():
        path = folder / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    return [f"contracts/{name}/v1/{rel}" for rel in files]


# ---------------------------------------------------------------- check (ASP-041)
def versions(repo: Path) -> list[Path]:
    root = repo / "contracts"
    if not root.is_dir():
        return []
    return sorted(v for c in root.iterdir() if c.is_dir() for v in c.iterdir() if v.is_dir() and VERSION_DIR_RE.match(v.name))


def _ajv_verdict(output: str) -> str:
    """'valid', 'invalid' or '' when ajv did not report (it could not run).

    ajv prints "<file> valid" or "<file> invalid" (then the errors): read the verdict at the END of a line, never in
    the path ("examples/invalid/x.json valid" is a valid result)."""
    match = re.search(r"\s(invalid|valid)\s*$", output, re.M)
    return match.group(1) if match else ""


def check(repo: Path, runner: Runner = default_runner) -> list[str]:
    """Problems found (empty = all contracts conform). Raises ContractError(code=2) if a validator cannot run."""
    problems: list[str] = []
    for folder in versions(repo):
        rel = folder.relative_to(repo).as_posix()
        schema, openapi = folder / "schema.json", folder / "openapi.yaml"
        if schema.exists() == openapi.exists():
            problems.append(f"{rel}: needs exactly one of schema.json or openapi.yaml")
            continue
        if not (folder / "README.md").is_file():
            problems.append(f"{rel}: README.md (provider, consumers) is missing")
        valid = sorted((folder / "examples" / "valid").glob("*.json"))
        invalid = sorted((folder / "examples" / "invalid").glob("*.json"))
        if not valid:
            problems.append(f"{rel}: examples/valid/ is empty")
        if schema.exists():
            if not invalid:
                problems.append(f"{rel}: examples/invalid/ is empty")
            for example, expected in [(e, "valid") for e in valid] + [(e, "invalid") for e in invalid]:
                cmd = [*npx_prefix(), AJV, "validate", "--spec=draft2020", "--strict=false",
                       "-s", str(schema), "-d", str(example)]
                _code, out = runner(cmd, repo)
                verdict = _ajv_verdict(out)
                if not verdict:
                    raise ContractError(f"ajv could not validate {example.relative_to(repo)}: {out.strip()[-300:]}", 2)
                if verdict != expected:
                    what = "valid example rejected" if expected == "valid" else "invalid example accepted"
                    problems.append(f"{example.relative_to(repo).as_posix()}: {what}")
        else:
            code, out = runner([*npx_prefix(), REDOCLY, "lint", str(openapi)], repo)
            if code != 0:
                if "npm ERR" in out or "command not found" in out or "ENOTFOUND" in out:
                    raise ContractError(f"redocly could not run: {out.strip()[-300:]}", 2)
                problems.append(f"{rel}/openapi.yaml: lint failed: {out.strip()[-300:]}")
    return problems


# ---------------------------------------------------------------- immutability (ASP-042)
def _git(repo: Path, *args: str) -> int:
    return subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True, check=False).returncode


def released_changes(repo: Path, ref: str = "origin/production") -> list[str]:
    """Released contract versions (present on `ref`) whose files differ in the working tree."""
    if _git(repo, "rev-parse", "--verify", "--quiet", ref) != 0:
        return []
    out = []
    for folder in versions(repo):
        rel = folder.relative_to(repo).as_posix()
        if _git(repo, "cat-file", "-e", f"{ref}:{rel}") != 0:
            continue
        if _git(repo, "diff", "--quiet", ref, "--", rel) != 0:
            name, version = folder.parent.name, folder.name
            nxt = int(VERSION_DIR_RE.match(version).group(1)) + 1  # type: ignore[union-attr]
            out.append(f"{rel}: released contract {name}/{version} is immutable: create v{nxt}")
    return out
