"""Digest, roles and human approval of a change (ASP-020 … ASP-023, ASP-117, ASP-118), stdlib only."""
from __future__ import annotations

import hashlib
import os
import re
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Callable

import ghcli

CHECKED_RE = re.compile(rb"^(\s*- )\[[xX]\]", re.M)
APPROVAL_RE = re.compile(r"<!-- ai-specs:approval digest=(sha256:[0-9a-f]{64}) commit=([0-9a-f]{7,40}) by=([A-Za-z0-9-]+) -->")
CARD_RECORD_RE = re.compile(r"<!-- ai-specs:approval digest=(sha256:[0-9a-f]{64}) commit=([0-9a-f]{7,40}) "
                            r"by=([A-Za-z0-9-]+) via=card run=(\d{1,20}) -->")
BOT_LOGIN = "github-actions[bot]"  # only a workflow's GITHUB_TOKEN writes as this login
CARD_WORKFLOW = ".github/workflows/ai-specs-approval.yml"
BLOCK_RE = re.compile(r"<!-- ai-specs:change -->(.*?)<!-- /ai-specs:change -->", re.S)
CLOSES_RE = re.compile(r"\b(?:close[sd]?|fix(?:e[sd])?|resolve[sd]?)\s+#(\d+)\b", re.I)
ROLE_KEYS = ("approvers", "reviewers", "releasers")


class ApprovalError(RuntimeError):
    """The approval cannot be given or checked; `code` is the exit code (1 refused/stale, 2 cannot check)."""

    def __init__(self, message: str, code: int = 1) -> None:
        super().__init__(message)
        self.code = code


# ---------------------------------------------------------------- digest (ASP-020)
def change_folder(repo: Path, change: str) -> Path:
    live = repo / "openspec" / "changes" / change
    if live.is_dir():
        return live
    archived = sorted((repo / "openspec" / "changes" / "archive").glob(f"*-{change}"))
    if archived:
        return archived[-1]
    raise ApprovalError(f"change '{change}' not found (live or archived)", 2)


def digest(folder: Path) -> str:
    h = hashlib.sha256()
    for path in sorted((p for p in folder.rglob("*") if p.is_file()), key=lambda p: p.relative_to(folder).as_posix()):
        rel = path.relative_to(folder).as_posix()
        data = path.read_bytes().replace(b"\r\n", b"\n")
        if rel == "tasks.md":
            data = CHECKED_RE.sub(rb"\1[ ]", data)
        h.update(rel.encode() + b"\0" + data)
    return "sha256:" + h.hexdigest()


# ---------------------------------------------------------------- roles (ASP-021)
@dataclass
class Roles:
    approvers: list[str] = field(default_factory=list)
    reviewers: list[str] = field(default_factory=list)
    releasers: list[str] = field(default_factory=list)
    min_approvals: int = 1


def parse_roles(text: str) -> Roles:
    """`key: [a, b]`, block lists (`key:` + `  - a`) and `min_approvals: N`; comments allowed. Anything else fails."""
    values: dict[str, list[str] | int] = {}
    current: str | None = None
    for n, raw in enumerate(text.splitlines(), 1):
        line = raw.split("#", 1)[0].rstrip()
        if not line.strip():
            continue
        item = re.match(r"^\s+-\s*([A-Za-z0-9-]+)\s*$", line)
        if item and current in ROLE_KEYS:
            values.setdefault(current, []).append(item.group(1))  # type: ignore[union-attr]
            continue
        m = re.match(r"^([a-z_]+):\s*(.*)$", line)
        if not m or m.group(1) not in (*ROLE_KEYS, "min_approvals"):
            raise ApprovalError(f"openspec/roles.yaml:{n}: unexpected line '{raw.strip()}'")
        key, rest = m.group(1), m.group(2).strip()
        current = key
        if key == "min_approvals":
            if not rest.isdigit():
                raise ApprovalError(f"openspec/roles.yaml:{n}: min_approvals must be an integer")
            values[key] = int(rest)
        elif rest.startswith("["):
            if not rest.endswith("]"):
                raise ApprovalError(f"openspec/roles.yaml:{n}: unclosed list")
            values[key] = [v.strip() for v in rest[1:-1].split(",") if v.strip()]
        elif rest:
            raise ApprovalError(f"openspec/roles.yaml:{n}: '{key}' must be a list")
        else:
            values[key] = []
    return Roles(**{k: v for k, v in values.items()})  # type: ignore[arg-type]


def read_roles(repo: Path) -> Roles:
    path = repo / "openspec" / "roles.yaml"
    if not path.is_file():
        raise ApprovalError("openspec/roles.yaml is missing (ai-specs init writes it)")
    return parse_roles(path.read_text(encoding="utf-8"))


def roles_errors(repo: Path) -> list[str]:
    try:
        roles = read_roles(repo)
    except ApprovalError as exc:
        return [str(exc)]
    errors = []
    if not roles.approvers:
        errors.append("openspec/roles.yaml: 'approvers' is empty")
    if roles.min_approvals < 1:
        errors.append("openspec/roles.yaml: min_approvals must be at least 1")
    elif roles.min_approvals > len(set(roles.approvers)):
        errors.append(f"openspec/roles.yaml: min_approvals {roles.min_approvals} exceeds the "
                      f"{len(set(roles.approvers))} approver(s)")
    return errors


def roles_template(owner: str) -> str:
    return (f"# Who may do what in this repo (ai-specs standard). GitHub logins.\n"
            f"approvers: [{owner}]     # approve specs before work starts (ai-specs approve)\n"
            f"reviewers: [{owner}]     # review PRs (CODEOWNERS is generated from this list)\n"
            f"releasers: [{owner}]     # merge release and promotion PRs\n"
            f"min_approvals: 1\n")


# ---------------------------------------------------------------- issue helpers
def change_of(issue_body: str) -> str:
    block = BLOCK_RE.search(issue_body or "")
    if block:
        m = re.search(r"^\s*change:\s*([a-z0-9][a-z0-9-]+)\s*$", block.group(1), re.M)
        if m:
            return m.group(1)
    raise ApprovalError("the issue has no ai-specs change block (create it with /hq-spec)", 2)


BRANCH_ISSUE_RE = re.compile(r"^(?:change|hotfix)/(\d+)-")


def issue_of_pr(repo: Path, pr: int) -> int:
    """`Closes #n` (exactly one) in the body, else the n of a `change/<n>-…` or `hotfix/<n>-…` head branch (ASP-024)."""
    data = ghcli.pull(repo, pr) or {}
    found = sorted(set(CLOSES_RE.findall(data.get("body") or "")))
    if len(found) == 1:
        return int(found[0])
    if len(found) > 1:
        raise ApprovalError(f"PR #{pr} closes several issues {found}: one change per PR")
    head = ((data.get("head") or {}).get("ref")) or ""
    match = BRANCH_ISSUE_RE.match(head)
    if match:
        return int(match.group(1))
    raise ApprovalError(f"PR #{pr} must close one issue ('Closes #<n>') or come from change/<n>-… or hotfix/<n>-…")


def _head(repo: Path) -> str:
    res = subprocess.run(["git", "-C", str(repo), "rev-parse", "HEAD"], capture_output=True, text=True, check=False)
    return res.stdout.strip() if res.returncode == 0 else "0000000"


# ---------------------------------------------------------------- approve (ASP-022)
def approve(repo: Path, number: int, ask: Callable[[str], str] = input,
            is_tty: Callable[[], bool] = lambda: sys.stdin.isatty() and sys.stdout.isatty(),
            say: Callable[[str], None] = print) -> None:
    if os.environ.get("CLAUDECODE"):
        raise ApprovalError("approval must be given by a person in their own terminal (agent session detected)")
    if not is_tty():
        raise ApprovalError("approval must be given by a person in their own terminal (no interactive terminal)")
    roles = read_roles(repo)
    try:
        who = ghcli.login(repo)
        data = ghcli.issue(repo, number)
    except ghcli.GhError as exc:
        raise ApprovalError(str(exc), 2) from exc
    if who not in roles.approvers:
        raise ApprovalError(f"{who} is not an approver of this repo (approvers: {', '.join(roles.approvers)})")
    change = change_of(data.get("body") or "")
    value = digest(change_folder(repo, change))
    commit = _head(repo)
    say(f"Issue #{number} · change '{change}' at commit {commit[:12]}\nDigest: {value}\n"
        "Approving freezes this exact scope: any later edit to proposal, specs, design or task wording needs a new approval.")
    typed = ask(f"Type the first 8 characters after 'sha256:' to approve: ").strip().lower()
    if typed != value.split(":", 1)[1][:8]:
        raise ApprovalError("confirmation did not match: nothing was approved")
    body = (f"<!-- ai-specs:approval digest={value} commit={commit} by={who} -->\n"
            f"Approved by @{who}: change `{change}` at `{commit[:12]}` (digest `{value[:19]}…`).")
    try:
        ghcli.comment(repo, number, body)
        ghcli.set_state(repo, number, "state:approved")
    except ghcli.GhError as exc:
        raise ApprovalError(str(exc), 2) from exc
    say(f"approved: #{number} is now state:approved")


# ---------------------------------------------------------------- check (ASP-023, ASP-117, ASP-118)
@dataclass
class Count:
    """Approvals of one digest: `valid` logins, `stale` digests seen, and why some card records did not count."""
    valid: set[str] = field(default_factory=set)
    stale: list[str] = field(default_factory=list)
    missing_runs: list[str] = field(default_factory=list)


def _time(text: str | None) -> datetime | None:
    try:
        return datetime.fromisoformat((text or "").replace("Z", "+00:00"))
    except ValueError:
        return None


def is_bot_note(note: dict) -> bool:
    user = note.get("user") or {}
    return user.get("login") == BOT_LOGIN and user.get("type") == "Bot"


def _run_proves(run: dict, note: dict, by: str, repo_meta: dict) -> bool:
    """The record was written by the card workflow of the default branch, triggered by `by` (design section 3)."""
    run_time, note_time = _time(run.get("created_at")), _time(note.get("created_at"))
    full_name = ((run.get("repository") or {}).get("full_name"))
    return (run.get("event") == "issue_comment"
            and run.get("path") == CARD_WORKFLOW
            and run.get("head_branch") == repo_meta.get("default_branch")
            and ((run.get("triggering_actor") or {}).get("login")) == by
            and run_time is not None and note_time is not None and run_time <= note_time
            and (full_name is None or full_name == repo_meta.get("full_name")))


def count_approvals(repo: Path, notes: list[dict], roles: Roles, current: str, verify_runs: bool = True) -> Count:
    """The one counting rule for `check-approval` and the card workflow.

    Terminal records count when their author is `by`; card records when the Actions bot wrote them and (with
    `verify_runs`) their run proves the card workflow of the default branch wrote them for `by`. Either kind stops
    counting once edited. The card workflow has no `actions: read`, so it counts with `verify_runs=False`: the label it
    sets is advisory, `check-approval` stays the authority. Raises ghcli.GhError when GitHub cannot answer.
    """
    count = Count()
    repo_meta: dict | None = None
    for note in notes:
        author = ((note.get("user") or {}).get("login")) or ""
        body = note.get("body") or ""
        if note.get("created_at") != note.get("updated_at"):
            continue  # an edited approval proves nothing (ASP-118)
        for value, _commit, by in APPROVAL_RE.findall(body):
            if by != author or by not in roles.approvers:
                continue  # forged or not an approver: ignored
            (count.valid.add(by) if value == current else count.stale.append(value))
        for value, _commit, by, run_id in CARD_RECORD_RE.findall(body):
            if not is_bot_note(note) or by not in roles.approvers:
                continue
            if value != current:
                count.stale.append(value)
                continue
            if by in count.valid:
                continue
            if verify_runs:
                if repo_meta is None:
                    repo_meta = ghcli.repo_info(repo)
                run = ghcli.run_info(repo, run_id)
                if run is None:
                    count.missing_runs.append(run_id)
                    continue
                if not _run_proves(run, note, by, repo_meta):
                    continue
            count.valid.add(by)
    return count


def check(repo: Path, number: int) -> str:
    """Returns a one-line success message or raises ApprovalError (code 1 not approved/stale, 2 cannot check)."""
    roles = read_roles(repo)
    try:
        data = ghcli.issue(repo, number)
        notes = ghcli.comments(repo, number)
    except ghcli.GhError as exc:
        raise ApprovalError(str(exc), 2) from exc
    change = change_of(data.get("body") or "")
    current = digest(change_folder(repo, change))
    try:
        count = count_approvals(repo, notes, roles, current)
    except ghcli.GhError as exc:
        raise ApprovalError(str(exc), 2) from exc
    if len(count.valid) >= roles.min_approvals:
        return f"approved: #{number} '{change}' by {', '.join(sorted(count.valid))} for {current}"
    if count.missing_runs:
        raise ApprovalError(f"card approval run {count.missing_runs[-1]} not found in this repo: approve again")
    if count.stale:
        raise ApprovalError(f"approved digest {count.stale[-1]} no longer matches {current}: the scope changed, "
                            "approve again")
    raise ApprovalError(f"#{number} '{change}' has {len(count.valid)} of {roles.min_approvals} approval(s) for {current}")
