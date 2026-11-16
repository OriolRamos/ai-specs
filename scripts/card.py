"""Approval card (ASP-111 … ASP-115): one sticky bot comment per change issue that shows, in plain language, what a
digest stands for, and turns a tick of its single checkbox by an approver into an approval record. Stdlib only.

The workflow (`kit/approval-card.yml.tmpl`) runs three commands, all through `ai_specs.py card`:
  resolve  which issue, change and branch an event is about; nothing is written
  render   (re)draw the card from the change folder at the branch head (`issues`, `push`)
  review   check a tick and record it, or undo it and say why (`issue_comment: edited`)

The change branch is data: files are read from its checkout and nothing in it is executed or imported. Identity comes
from the event (`sender.login`), never from comment text. GitHub calls go through `ghcli`; any failure is exit 2.
"""
from __future__ import annotations

import re
import subprocess
import tarfile
import tempfile
from dataclasses import dataclass
from pathlib import Path

import approval
import ghcli

CHANGE_ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]{1,79}$")
CARD_PREFIX = "<!-- ai-specs:approval-card "
CARD_MARKER_RE = re.compile(r"\A<!-- ai-specs:approval-card change=([a-z0-9][a-z0-9-]{1,79}) issue=(\d+) "
                            r"digest=(sha256:[0-9a-f]{64}) commit=([0-9a-f]{40}) -->\n")
SCOPE_END = "<!-- ai-specs:approval-card-scope-end -->"
CHECKBOX_RE = re.compile(r"^- \[([ xX])\] I approve exactly this scope \(digest ([0-9a-f]{8})\)[ \t]*$", re.M)
PUSH_REF_RE = re.compile(r"^refs/heads/(change/(\d{1,9})-[a-z0-9][a-z0-9-]*)$")
SIZE_RE = re.compile(r"^\*\*Size:\*\*\s*([SML])\b", re.M)
TASK_RE = re.compile(r"^\s*- \[[ xX]\]\s+(\d+(?:\.\d+)*)\s+(.*)$")
HEADING_RE = re.compile(r"^## +(.+?)\s*$", re.M)
LIMITS = (("Why", "why", 600), ("What changes", "what changes", 1500), ("Not to add", "not to add", 800))
CARD_CAP = 60_000  # GitHub refuses comments over 65 536 characters
TASK_TEXT = 80
# Fixed kit list (no roles.yaml key: its parser is strict and adopting repos would break).
SENSITIVE = (".github/workflows/", ".github/CODEOWNERS", "CODEOWNERS", "openspec/roles.yaml", "openspec/config.yaml",
             "contracts/", "scripts/")
ACTIVE_STATES = ("state:approved", "state:in-progress", "state:in-review")

NOT_APPROVER = "Your tick was undone: @{who} is not an approver of this repo."
STALE = "Your tick was undone: the scope changed since this card was drawn. Review it again."
ALTERED = "Your tick was undone: the card text was changed; it has been restored. Review it again."
NOT_STICKY = "This is not the approval card of this issue: use the first card."
NOT_OPEN_CHANGE = "Your tick was undone: the issue is not an open change."


class CardError(RuntimeError):
    """The card command cannot run (bad event, missing run id); `code` like check-approval (2 = cannot check)."""

    def __init__(self, message: str, code: int = 2) -> None:
        super().__init__(message)
        self.code = code


# ---------------------------------------------------------------- render (ASP-111)
@dataclass(frozen=True)
class Meta:
    """Everything the scope section depends on besides the folder's files."""
    change: str
    issue: int
    branch: str
    commit: str
    repo_url: str
    folder_rel: str  # the change folder relative to the repo root (live or archived)


def strip_comments(text: str) -> str:
    """No HTML comment, nor half of one, survives: a proposal cannot forge a marker or end the scope early."""
    previous = None
    while previous != text:
        previous = text
        text = re.sub(r"<!--.*?-->", "", text, flags=re.S).replace("<!--", "").replace("-->", "")
    return text


def sections(text: str) -> dict[str, str]:
    found: dict[str, str] = {}
    matches = list(HEADING_RE.finditer(text))
    for i, match in enumerate(matches):
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        found.setdefault(match.group(1).strip().lower(), text[match.end():end].strip("\n").rstrip())
    return found


def truncate(text: str, limit: int, link: str) -> str:
    """At most `limit` characters, cut at a line end, then a link to the full text."""
    if len(text) <= limit:
        return text
    cut = text.rfind("\n", 0, limit)
    kept = text[:cut if cut > 0 else limit].rstrip()
    if sum(1 for line in kept.splitlines() if line.lstrip().startswith("```")) % 2:
        kept += "\n```"  # never leave a code fence open over the rest of the card
    return f"{kept}\n… [read the full proposal]({link})"


def requirement_titles(folder: Path) -> list[str]:
    titles = []
    for spec in sorted((folder / "specs").rglob("spec.md")) if (folder / "specs").is_dir() else []:
        for line in spec.read_text(encoding="utf-8").splitlines():
            if line.startswith("### Requirement:"):
                titles.append(strip_comments(line[len("### Requirement:"):]).strip())
    return titles


def task_lines(folder: Path) -> tuple[int, list[str]]:
    """The task count and the `(human gate…)` tasks as `<number> <first 80 characters>`."""
    path = folder / "tasks.md"
    if not path.is_file():
        return 0, []
    count, gates = 0, []
    for line in path.read_text(encoding="utf-8").splitlines():
        match = TASK_RE.match(line)
        if not match:
            continue
        count += 1
        if "(human gate" in line.lower():
            text = strip_comments(match.group(2)).strip()
            gates.append(f"{match.group(1)} {text[:TASK_TEXT].rstrip()}{'…' if len(text) > TASK_TEXT else ''}")
    return count, gates


def sensitive_paths(folder: Path) -> list[str]:
    """Entries of the kit list named by a backticked path (no spaces) in proposal, design or tasks."""
    tokens: set[str] = set()
    for name in ("proposal.md", "design.md", "tasks.md"):
        path = folder / name
        if path.is_file():
            tokens |= {t.removeprefix("./") for t in re.findall(r"`([^`\s]+)`", path.read_text(encoding="utf-8"))}
    found = []
    for entry in SENSITIVE:
        if entry.endswith("/"):
            hit = any(t.startswith(entry) or t == entry[:-1] for t in tokens)
        else:
            hit = entry in tokens
        if hit:
            found.append(entry)
    return found


def _listing(items: list[str], limit: int | None) -> list[str]:
    shown = items if limit is None else items[:limit]
    lines = [f"- {item}" for item in shown]
    if len(shown) < len(items):
        lines.append(f"- and {len(items) - len(shown)} more")
    return lines


def render_scope(folder: Path, meta: Meta, value: str, req_limit: int | None = None,
                 gate_limit: int | None = None) -> str:
    """The scope section: a pure function of the folder, `meta` and the digest (two renders are byte-identical)."""
    blob = f"{meta.repo_url}/blob/{meta.commit}/{meta.folder_rel}"
    proposal = (folder / "proposal.md").read_text(encoding="utf-8") if (folder / "proposal.md").is_file() else ""
    size = SIZE_RE.search(proposal)
    parts = sections(strip_comments(proposal))
    lines = [f"{CARD_PREFIX}change={meta.change} issue={meta.issue} digest={value} commit={meta.commit} -->",
             f"### Approval card · `{meta.change}` · size {size.group(1) if size else '?'}",
             f"Issue #{meta.issue} · branch `{meta.branch}` at [`{meta.commit[:12]}`]({meta.repo_url}/commit/"
             f"{meta.commit}) · digest `{value.split(':', 1)[1][:8]}`", ""]
    for title, key, limit in LIMITS:
        text = parts.get(key, "").strip() or "_(missing in proposal.md)_"
        lines += [f"**{title}**", truncate(text, limit, f"{blob}/proposal.md"), ""]
    titles = requirement_titles(folder)
    lines += [f"**Requirements ({len(titles)})**", *(_listing(titles, req_limit) or ["- none"]), ""]
    count, gates = task_lines(folder)
    lines.append(f"**Tasks** {count}, of which **{len(gates)} human gate**" + (":" if gates else ""))
    lines += _listing(gates, gate_limit)
    named = sensitive_paths(folder)
    lines += ["", "**Sensitive paths named:** " + (", ".join(f"`{p}`" for p in named) if named else "none"), ""]
    links = [f"[proposal]({blob}/proposal.md)"]
    if (folder / "design.md").is_file():
        links.append(f"[design]({blob}/design.md)")
    if (folder / "specs").is_dir():
        links.append(f"[specs]({meta.repo_url}/tree/{meta.commit}/{meta.folder_rel}/specs)")
    links.append(f"[tasks]({blob}/tasks.md)")
    lines += ["Read before approving: " + " · ".join(links), "", SCOPE_END]
    return "\n".join(lines)


def render_status(value: str, approvers: list[str], needed: int, status: str = "") -> str:
    """The status section: the unticked box, the approvals so far and an optional status line."""
    if approvers:
        done = f"Approvals for this digest: {', '.join('@' + a for a in approvers)} ({len(approvers)} of {needed})."
    else:
        done = f"Approvals for this digest: none yet ({needed} needed)."
    lines = ["", f"- [ ] I approve exactly this scope (digest {value.split(':', 1)[1][:8]})", "",
             done + " Only approvers in `openspec/roles.yaml` can approve."]
    if status:
        lines.append(status)
    return "\n".join(lines) + "\n"


def render(folder: Path, meta: Meta, approvers: list[str] | None = None, needed: int = 1, status: str = "") -> str:
    """The whole card, at most CARD_CAP characters: the requirements list is cut first, then the human-gate list."""
    value = approval.digest(folder)
    tail = render_status(value, sorted(approvers or []), needed, status)
    titles, (_count, gates) = requirement_titles(folder), task_lines(folder)
    req_limit: int | None = None
    gate_limit: int | None = None
    while True:
        body = render_scope(folder, meta, value, req_limit, gate_limit) + tail
        if len(body) <= CARD_CAP:
            return body
        if req_limit is None or req_limit > 0:
            req_limit = (len(titles) if req_limit is None else req_limit) // 2
        elif gate_limit is None or gate_limit > 0:
            gate_limit = (len(gates) if gate_limit is None else gate_limit) // 2
        else:
            return body[:CARD_CAP]  # unreachable with the section limits above; never post an over-long comment


def split(body: str) -> tuple[str, str]:
    """(scope section ending with the scope-end marker, status section); line endings normalised to LF."""
    text = body.replace("\r\n", "\n")
    index = text.find(SCOPE_END)
    if index == -1:
        return text, ""
    end = index + len(SCOPE_END)
    return text[:end], text[end:]


# ---------------------------------------------------------------- resolve (ASP-112)
@dataclass
class Target:
    """What an event is about. `proceed` is False with a `reason` when nothing may be written."""
    proceed: bool
    reason: str = ""
    issue: int = 0
    change: str = ""
    branch: str = ""
    labels: tuple[str, ...] = ()


def branch_of(issue_body: str) -> str:
    block = approval.BLOCK_RE.search(issue_body or "")
    if block:
        match = re.search(r"^\s*branch:\s*(\S+)\s*$", block.group(1), re.M)
        if match:
            return match.group(1)
    return ""


def resolve(repo: Path, event: dict) -> Target:
    """Validates the issue and branch of an `issues`, `issue_comment` or `push` event (design section 1)."""
    pushed = ""
    if "issue" in event:
        issue = event["issue"] or {}
    else:
        if event.get("deleted"):
            return Target(False, "the branch was deleted")
        match = PUSH_REF_RE.match(str(event.get("ref") or ""))
        if not match:
            return Target(False, f"push to {event.get('ref')!r} is not a change branch")
        pushed = match.group(1)
        try:
            issue = ghcli.issue(repo, int(match.group(2))) or {}
        except ghcli.GhError as exc:
            if "HTTP 404" in str(exc):
                return Target(False, f"issue #{match.group(2)} does not exist")
            raise
    number = int(issue.get("number") or 0)
    labels = tuple(sorted(lab.get("name", "") for lab in issue.get("labels") or []))
    if issue.get("pull_request"):
        return Target(False, f"#{number} is a pull request")
    if issue.get("state") != "open":
        return Target(False, f"#{number} is closed")
    if "type:change" not in labels:
        return Target(False, f"#{number} is not labelled type:change")
    body = issue.get("body") or ""
    if not approval.BLOCK_RE.search(body):
        return Target(False, f"#{number} has no ai-specs change block")
    try:
        change = approval.change_of(body)
    except approval.ApprovalError:
        return Target(False, f"#{number}: the block names no valid change id")
    if not CHANGE_ID_RE.match(change):
        return Target(False, f"#{number}: invalid change id")
    branch = branch_of(body)
    if not re.fullmatch(rf"change/{number}-[a-z0-9][a-z0-9-]*", branch):
        return Target(False, f"#{number}: the block's branch is not change/{number}-<slug>")
    if pushed and pushed != branch:
        return Target(False, f"{pushed} is not the branch #{number} names ({branch}): ignored")
    if ghcli.branch_head(repo, branch) is None:
        return Target(False, f"branch {branch} does not exist yet")
    return Target(True, "", number, change, branch, labels)


# ---------------------------------------------------------------- shared helpers
def git_head(src: Path) -> str:
    res = subprocess.run(["git", "-C", str(src), "rev-parse", "HEAD"], capture_output=True, text=True, check=False)
    sha = res.stdout.strip()
    if res.returncode != 0 or not re.fullmatch(r"[0-9a-f]{40}", sha):
        raise CardError(f"cannot read the head commit of {src}")
    return sha


def digest_at(src: Path, commit: str, folder_rel: str) -> str | None:
    """approval.digest of the folder as it was at `commit` (an ancestor of HEAD), or None when it cannot be read."""
    def git(*args: str) -> subprocess.CompletedProcess:
        return subprocess.run(["git", "-C", str(src), *args], capture_output=True, check=False)

    if git("merge-base", "--is-ancestor", commit, "HEAD").returncode != 0:
        return None
    archive = git("archive", "--format=tar", commit, "--", folder_rel)
    if archive.returncode != 0:
        return None
    with tempfile.TemporaryDirectory() as tmp:
        tar_path = Path(tmp) / "folder.tar"
        tar_path.write_bytes(archive.stdout)
        with tarfile.open(tar_path) as tar:
            tar.extractall(Path(tmp) / "x", filter="data")
        folder = Path(tmp) / "x" / folder_rel
        return approval.digest(folder) if folder.is_dir() else None


def find_cards(notes: list[dict]) -> list[dict]:
    """Card comments by the Actions bot, oldest first: the first one is the sticky card."""
    return [n for n in notes if approval.is_bot_note(n) and (n.get("body") or "").startswith(CARD_PREFIX)]


def marker(body: str) -> dict | None:
    match = CARD_MARKER_RE.match(body.replace("\r\n", "\n"))
    if not match:
        return None
    return {"change": match.group(1), "issue": int(match.group(2)), "digest": match.group(3),
            "commit": match.group(4)}


def repo_url(event: dict) -> str:
    url = str(((event.get("repository") or {}).get("html_url")) or "")
    if not re.fullmatch(r"https://[A-Za-z0-9.-]+/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", url):
        raise CardError("the event has no repository URL")
    return url


def _load(base: Path, src: Path, target: Target, event: dict) -> tuple[Path, str, str, Meta]:
    """(folder, digest, head, meta at head) of the change in the branch checkout."""
    folder = approval.change_folder(src, target.change)
    head = git_head(src)
    meta = Meta(target.change, target.issue, target.branch, head, repo_url(event),
                folder.resolve().relative_to(src.resolve()).as_posix())
    return folder, approval.digest(folder), head, meta


def _approvers(base: Path, number: int, roles: approval.Roles, value: str) -> list[str]:
    notes = ghcli.comments(base, number)
    return sorted(approval.count_approvals(base, notes, roles, value, verify_runs=False).valid)


# ---------------------------------------------------------------- sync (ASP-111, ASP-112)
def sync(base: Path, src: Path, event: dict) -> str:
    """Creates or updates the sticky card for the head of the change branch. Returns what it did, for the log."""
    target = resolve(base, event)
    if not target.proceed:
        return f"notice: nothing to render: {target.reason}"
    try:
        folder, value, _head, meta = _load(base, src, target, event)
    except approval.ApprovalError:
        return f"notice: nothing to render: the change folder '{target.change}' is not on {target.branch} yet"
    roles = approval.read_roles(base)
    notes = ghcli.comments(base, target.issue)
    cards = find_cards(notes)
    current = marker(cards[0]["body"]) if cards else None
    if current and (current["change"], current["issue"], current["digest"]) == (target.change, target.issue, value):
        return f"card of #{target.issue} is up to date (digest {value[7:15]})"
    approvers = sorted(approval.count_approvals(base, notes, roles, value, verify_runs=False).valid)
    body = render(folder, meta, approvers, roles.min_approvals)
    if cards:
        ghcli.edit_comment(base, cards[0]["id"], body)
        if current and current["digest"] != value and set(target.labels) & set(ACTIVE_STATES):
            ghcli.set_state(base, target.issue, "state:proposed")
            return f"card of #{target.issue} redrawn for a new digest {value[7:15]}; issue back to state:proposed"
        return f"card of #{target.issue} redrawn (digest {value[7:15]})"
    ghcli.comment(base, target.issue, body)
    return f"card of #{target.issue} posted (digest {value[7:15]})"


# ---------------------------------------------------------------- review (ASP-113, ASP-114, ASP-115)
def _unticked(body: str, reason: str) -> str:
    """The edited card with its box cleared and the reason, for a card that cannot be redrawn from a head."""
    scope, status = split(body)
    found = marker(scope)
    short = found["digest"][7:15] if found else "????????"
    return f"{scope}\n- [ ] I approve exactly this scope (digest {short})\n\n{reason}\n"


def _record(value: str, head: str, sender: str, run_id: str, change: str) -> str:
    return (f"<!-- ai-specs:approval digest={value} commit={head} by={sender} via=card run={run_id} -->\n"
            f"Approved by @{sender} from the approval card: change `{change}` at `{head[:12]}` "
            f"(digest `{value[7:15]}`).\n"
            "If you did not tick this box, delete this comment: the approval then no longer counts.")


def _promote(base: Path, number: int, count: int, needed: int) -> None:
    """`state:approved` once enough approvals exist; a later state (in progress, in review) is left alone."""
    if count < needed:
        return
    labels = {lab["name"] for lab in (ghcli.issue(base, number).get("labels") or [])}
    if not labels & set(ACTIVE_STATES):
        ghcli.set_state(base, number, "state:approved")


def review(base: Path, src: Path, event: dict, run_id: str) -> tuple[int, str]:
    """Handles an edit of a card comment. Returns (exit code, message): 0 recorded or restored, 1 tick undone."""
    if not re.fullmatch(r"\d{1,20}", run_id or ""):
        raise CardError("GITHUB_RUN_ID is missing: card review runs only inside the workflow")
    comment = event.get("comment") or {}
    sender = (event.get("sender") or {})
    who = str(sender.get("login") or "")
    body = str(comment.get("body") or "")
    if (not approval.is_bot_note(comment) or not body.startswith(CARD_PREFIX) or sender.get("type") == "Bot"
            or (event.get("issue") or {}).get("pull_request")):
        return 0, "notice: not a person's edit of an approval card"
    number = int((event.get("issue") or {}).get("number") or 0)
    roles = approval.read_roles(base)
    notes = ghcli.comments(base, number)
    cards = find_cards(notes)
    edited = marker(body)
    target = resolve(base, event)
    loaded = None
    if target.proceed and edited and edited["change"] == target.change and edited["issue"] == number:
        try:
            loaded = _load(base, src, target, event)
        except approval.ApprovalError:
            loaded = None

    def redraw(status: str, meta: Meta | None = None) -> str:
        assert loaded is not None
        folder, value, _head, head_meta = loaded
        return render(folder, meta or head_meta, _approvers(base, number, roles, value), roles.min_approvals, status)

    def undo(reason: str, meta: Meta | None = None) -> tuple[int, str]:
        ghcli.edit_comment(base, comment["id"], redraw(reason, meta) if loaded else _unticked(body, reason))
        return 1, reason

    scope, status = split(body)
    ticked = any(m.group(1) in "xX" for m in CHECKBOX_RE.finditer(status))
    if not cards or cards[0].get("id") != comment.get("id"):
        return undo(NOT_STICKY)
    if loaded is None:
        return undo(NOT_OPEN_CHANGE) if ticked else (0, f"notice: nothing to redraw: {target.reason}")
    folder, value, head, head_meta = loaded
    # The card may have been drawn at an older commit with the same digest (a push that only ticked tasks).
    shown = head_meta
    if edited and edited["digest"] == value and edited["commit"] != head \
            and digest_at(src, edited["commit"], head_meta.folder_rel) == value:
        shown = Meta(**{**head_meta.__dict__, "commit": edited["commit"]})
    if not ticked:
        fresh = redraw("", shown)
        if fresh != body.replace("\r\n", "\n"):
            ghcli.edit_comment(base, comment["id"], fresh)
        return 0, "edit without a tick: card redrawn"
    if who not in roles.approvers:
        return undo(NOT_APPROVER.format(who=who), shown)
    if not edited or edited["digest"] != value:
        return undo(STALE)
    if scope != render_scope(folder, shown, value):
        return undo(ALTERED, shown)
    before = approval.count_approvals(base, notes, roles, value, verify_runs=False)
    if who not in before.valid:
        ghcli.comment(base, number, _record(value, head, who, run_id, target.change))
    first = sorted(approval.count_approvals(base, ghcli.comments(base, number), roles, value, verify_runs=False).valid)
    _promote(base, number, len(first), roles.min_approvals)
    again = sorted(approval.count_approvals(base, ghcli.comments(base, number), roles, value, verify_runs=False).valid)
    if again != first:  # another approver's record landed meanwhile: the label follows the newer count
        _promote(base, number, len(again), roles.min_approvals)
    ghcli.edit_comment(base, comment["id"], render(folder, shown, again, roles.min_approvals))
    return 0, f"approval of @{who} recorded for {value[:15]}… ({len(again)} of {roles.min_approvals})"
