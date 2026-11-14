#!/usr/bin/env python3
"""ai-specs: apply the ai-specs standard (docs/standard.md) to a repo and check its OpenSpec changes (stdlib only).

Commands:
  init <repo> --prefix LB [--project NAME] [--language English]
      Write openspec/config.yaml from the kit, create openspec/specs and openspec/changes, and add the managed
      ai-specs block to the repo's AGENTS.md (or CLAUDE.md). Idempotent. Refuses a repo that already runs another
      spec process (an openspec/config.yaml not written by ai-specs, or an Azure DevOps process skill).
  scaffold <repo> <change-id> --size S|M|L [--capability NAME]
      Create the change folder if needed and the artifacts its size requires, from the kit templates.
      Never overwrites an existing file.
  lint <repo> [<change-id> ...]
      Check active changes against the standard: size line, required sections, requirement ids, a Proof line in
      every scenario, task format, no TODO left. Exit 1 on errors.
  doctor <repo> [--json]
      Report which process the repo runs, the kit version, the openspec command to use and the lint state.
  digest <repo> <change-id>
      Print the change's digest (ASP-020): ticking tasks does not change it; any scope edit does.
  approve <repo> <issue>
      Human approval of the change linked to the issue (ASP-022). Run it yourself, in your own terminal.
  check-approval <repo> (<issue> | --pr <n>)
      Exit 0 when the approvers approved the current digest, 1 when not or stale, 2 when it cannot check (ASP-023).
  contract new <repo> <name> --kind jsonschema|openapi · contract check <repo>
      Versioned contract skeleton; conformance of every contract (pinned validators through npx) (ASP-040/041).
  catalog check <platform> · impact <platform> <id>
      Product catalog of a platform repo; what an id touches (ASP-050/051).
  adr new <repo> "<title>"
      Next numbered ADR in docs/adr/ from the template (ASP-070).
Init options: --owner (roles.yaml), --gate "<command>" (CI gate job), --kit-repo owner/ai-specs (CI checkout),
--platform [--product <id>] (a product platform repo: catalog, shared contracts, cross-repo ADRs).
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))  # also when run through the ~/.local/bin symlink
import approval  # noqa: E402
import catalog  # noqa: E402
import contracts  # noqa: E402

KIT = Path(__file__).resolve().parent.parent
VERSION = (KIT / "VERSION").read_text(encoding="utf-8").strip()
OPENSPEC_VERSION = "1.13.1"
MARKER = re.compile(r"^# ai-specs:kit version=(?P<version>\S+) prefix=(?P<prefix>[A-Z][A-Z0-9]*)", re.M)
PREFIX_RE = re.compile(r"^[A-Z][A-Z0-9]{1,9}$")
CHANGE_ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]{1,79}$")
BLOCK_BEGIN = "<!-- ai-specs:begin"
BLOCK_END = "<!-- ai-specs:end -->"
SIZES = ("S", "M", "L")
SIZE_RE = re.compile(r"^\*\*Size:\*\*\s*([SML])\b", re.M)
HEADING_RE = re.compile(r"^##\s+(.+?)\s*$", re.M)
TASK_RE = re.compile(r"^\s*- \[[ xX]\]\s+(.*)$")
TODO_RE = re.compile(r"\bTODO\b")
FOREIGN_SKILLS = (".agents/skills/azure-devops", ".claude/skills/azure-devops")


class AiSpecsError(RuntimeError):
    """A command cannot run on this repo."""


# ---------------------------------------------------------------- repo state
@dataclass
class RepoState:
    path: Path
    process: str  # ai-specs | foreign | none
    reason: str = ""
    version: str = ""
    prefix: str = ""
    changes: list[str] = field(default_factory=list)


def read_state(repo: Path) -> RepoState:
    config = repo / "openspec" / "config.yaml"
    for skill in FOREIGN_SKILLS:
        if (repo / skill).exists():
            return RepoState(repo, "foreign", f"{skill} drives this repo's change process")
    if config.is_file():
        match = MARKER.search(config.read_text(encoding="utf-8"))
        if not match:
            return RepoState(repo, "foreign", "openspec/config.yaml was not written by ai-specs")
        changes_dir = repo / "openspec" / "changes"
        changes = sorted(d.name for d in changes_dir.iterdir() if d.is_dir() and d.name != "archive") \
            if changes_dir.is_dir() else []
        return RepoState(repo, "ai-specs", "", match["version"], match["prefix"], changes)
    return RepoState(repo, "none", "no openspec/config.yaml")


def openspec_command(repo: Path) -> str:
    local = repo / "node_modules" / ".bin" / "openspec"
    if local.exists():
        return str(local)
    if shutil.which("openspec"):
        return "openspec"
    return f"npx -y @fission-ai/openspec@{OPENSPEC_VERSION}"


# ---------------------------------------------------------------- init
def render(text: str, **values: str) -> str:
    for key, value in values.items():
        text = text.replace("{{" + key + "}}", value)
    return text


def write_block(target: Path, block: str) -> None:
    text = target.read_text(encoding="utf-8") if target.exists() else ""
    begin, end = text.find(BLOCK_BEGIN), text.find(BLOCK_END)
    if begin != -1 and end != -1:
        text = text[:begin] + block.rstrip("\n") + text[end + len(BLOCK_END):]
    else:
        text = (text.rstrip("\n") + "\n\n" if text.strip() else "") + block
    target.write_text(text if text.endswith("\n") else text + "\n", encoding="utf-8")


NO_GATE = 'echo "Declare this repo\'s gate: ai_specs.py init . --prefix <P> --gate \"<command>\"" && exit 1'
ADR_TEMPLATE = """# ADR-{number:04d} · {title}

- **Date:** {date} · **Status:** proposed

## Context
TODO: the forces at play and why a decision is needed now.

## Decision
TODO: what was decided, in one paragraph.

## Consequences
TODO: what becomes easier, what becomes harder, and what to watch.
"""


def kit_repo_default() -> str:
    res = subprocess.run(["git", "-C", str(KIT), "remote", "get-url", "origin"], capture_output=True, text=True,
                         check=False)
    match = re.search(r"github\.com[:/]([^/]+/[^/]+?)(?:\.git)?$", res.stdout.strip())
    return match.group(1) if match else ""


def cmd_init(repo: Path, prefix: str, project: str, language: str, owner: str | None = None,
             gate: str | None = None, kit_repo: str | None = None, platform: bool = False,
             product: str | None = None) -> list[str]:
    if not PREFIX_RE.match(prefix):
        raise AiSpecsError(f"prefix '{prefix}' must be 2-10 upper-case letters or digits, starting with a letter")
    state = read_state(repo)
    if state.process == "foreign":
        raise AiSpecsError(f"{repo} already runs another spec process ({state.reason}); ai-specs will not touch it")
    if state.process == "ai-specs" and state.prefix != prefix:
        raise AiSpecsError(f"{repo} uses prefix {state.prefix}; requirement ids never change once archived")
    done = []
    openspec = repo / "openspec"
    for sub in ("specs", "changes"):
        folder = openspec / sub
        folder.mkdir(parents=True, exist_ok=True)
        keep = folder / ".gitkeep"
        if not any(folder.iterdir()):
            keep.write_text("", encoding="utf-8")
    roles = openspec / "roles.yaml"
    if not roles.exists():
        if not owner:
            try:
                owner = approval.ghcli.login(repo)
            except approval.ghcli.GhError as exc:
                raise AiSpecsError(f"openspec/roles.yaml needs an owner: pass --owner <github-login> ({exc})") from exc
        roles.write_text(approval.roles_template(owner), encoding="utf-8")
        done.append(f"openspec/roles.yaml (approver: {owner})")
    values = {"VERSION": VERSION, "PREFIX": prefix, "PROJECT": project, "LANGUAGE": language}
    (openspec / "config.yaml").write_text(render((KIT / "kit" / "config.yaml.tmpl").read_text(encoding="utf-8"),
                                                 **values), encoding="utf-8")
    done.append("openspec/config.yaml")
    target = next((repo / n for n in ("AGENTS.md", "CLAUDE.md") if (repo / n).is_file()), repo / "AGENTS.md")
    write_block(target, render((KIT / "kit" / "agents-block.md").read_text(encoding="utf-8"), **values))
    done.append(f"{target.name} (ai-specs block)")
    workflow = repo / ".github" / "workflows" / "ai-specs.yml"
    old_gate = WORKFLOW_GATE_RE.search(workflow.read_text(encoding="utf-8")) if workflow.exists() else None
    gate_cmd = gate or (old_gate.group(1).strip() if old_gate else NO_GATE)
    kit_ref = kit_repo or kit_repo_default() or ("self" if repo.resolve() == KIT.resolve() else "")
    if not kit_ref:
        raise AiSpecsError("cannot tell the ai-specs GitHub repo for CI: pass --kit-repo <owner>/<repo>")
    workflow.parent.mkdir(parents=True, exist_ok=True)
    text = render((KIT / "kit" / "workflow.yml.tmpl").read_text(encoding="utf-8"), VERSION=VERSION,
                  KIT_REPO=kit_ref, OPENSPEC_VERSION=OPENSPEC_VERSION, GATE=gate_cmd)
    if repo.resolve() == KIT.resolve():  # the kit checks itself with the code of the same commit, not a release tag
        text = re.sub(r"      # kit-checkout:begin\n.*?      # kit-checkout:end\n", "", text, flags=re.S)
        text = text.replace(".ai-specs-kit/scripts/", "scripts/")
    workflow.write_text(text, encoding="utf-8")
    done.append(".github/workflows/ai-specs.yml" + ("" if gate_cmd != NO_GATE else " (no gate yet: pass --gate)"))
    if platform:
        product_json = repo / "catalog" / "product.json"
        if not product_json.exists():
            product_json.parent.mkdir(parents=True, exist_ok=True)
            name = product or re.sub(r"-platform$", "", repo.name)
            product_json.write_text(json.dumps(catalog.skeleton(name), indent=2) + "\n", encoding="utf-8")
            done.append("catalog/product.json")
        for sub_dir in ("contracts", "docs/adr"):
            folder = repo / sub_dir
            folder.mkdir(parents=True, exist_ok=True)
            if not any(folder.iterdir()):
                (folder / ".gitkeep").write_text("", encoding="utf-8")
        done.append("contracts/, docs/adr/ (platform)")
    return done


WORKFLOW_GATE_RE = re.compile(r"- name: Repo gate\n\s+run: \|\n\s+(.+)\n?")


def cmd_adr(repo: Path, title: str) -> Path:
    folder = repo / "docs" / "adr"
    folder.mkdir(parents=True, exist_ok=True)
    numbers = [int(m.group(1)) for p in folder.glob("*.md") if (m := re.match(r"(\d{4})-", p.name))]
    number = max(numbers, default=0) + 1
    slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")[:60]
    path = folder / f"{number:04d}-{slug}.md"
    path.write_text(ADR_TEMPLATE.format(number=number, title=title, date=date.today().isoformat()), encoding="utf-8")
    return path


# ---------------------------------------------------------------- scaffold
def proposal_text(size: str) -> str:
    parts = [f"**Size:** {size}", "",
             "## Why", "TODO: what happens today, who it affects, why now.", "",
             "## What Changes", "- TODO", "- **Excludes:** TODO", "",
             "## Not to add", "- TODO: what an agent might add unasked."]
    if size in ("M", "L"):
        parts += ["", "## Prior art and reuse", "- TODO: reuse / extend / build new, and why."]
    if size == "M":
        parts += ["", "## Change impact",
                  "| Changed (symbol / endpoint / table / event) | Used by today | Breaks? | Mitigation / rollback |",
                  "|---|---|---|---|", "| TODO | | | |"]
    return "\n".join(parts) + "\n"


def cmd_scaffold(repo: Path, change: str, size: str, capability: str | None) -> list[str]:
    state = read_state(repo)
    if state.process != "ai-specs":
        raise AiSpecsError(f"{repo} does not run ai-specs ({state.reason or state.process}); run init first")
    if not CHANGE_ID_RE.match(change):
        raise AiSpecsError(f"change id '{change}' must be kebab-case")
    if size not in SIZES:
        raise AiSpecsError(f"size must be one of {', '.join(SIZES)}")
    folder = repo / "openspec" / "changes" / change
    folder.mkdir(parents=True, exist_ok=True)
    files = {".openspec.yaml": f"schema: spec-driven\ncreated: {date.today().isoformat()}\n",
             "proposal.md": proposal_text(size),
             "tasks.md": (KIT / "kit" / "templates" / "tasks.md").read_text(encoding="utf-8")}
    if size == "L":
        files["design.md"] = (KIT / "kit" / "templates" / "design.md").read_text(encoding="utf-8")
    if capability:
        spec = (KIT / "kit" / "templates" / "spec.md").read_text(encoding="utf-8")
        files[f"specs/{capability}/spec.md"] = render(spec, PREFIX=state.prefix)
    written = []
    for rel, text in files.items():
        path = folder / rel
        if path.exists():
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        written.append(f"openspec/changes/{change}/{rel}")
    return written


# ---------------------------------------------------------------- lint
def headings(text: str) -> set[str]:
    return {h.strip().lower() for h in HEADING_RE.findall(text)}


def lint_specs(spec: Path, rel: str, prefix: str, errors: list[str]) -> None:
    id_re = re.compile(rf"\b{re.escape(prefix)}-\d{{3}}\b" if prefix else r"\b[A-Z][A-Z0-9]*-\d{3}\b")
    section = ""
    scenario_line = 0
    scenario_has_proof = True
    lines = spec.read_text(encoding="utf-8").splitlines()

    def close_scenario() -> None:
        if scenario_line and not scenario_has_proof:
            errors.append(f"{rel}:{scenario_line}: scenario without a '- **Proof:**' line")

    for n, line in enumerate(lines, 1):
        if line.startswith("## "):
            close_scenario()
            scenario_line = 0
            section = line[3:].strip().split()[0].upper() if line[3:].strip() else ""
        elif line.startswith("### Requirement:"):
            close_scenario()
            scenario_line = 0
            if section in ("ADDED", "MODIFIED") and not id_re.search(line):
                errors.append(f"{rel}:{n}: requirement title needs an id like {prefix or 'ABC'}-001")
        elif line.startswith("#### Scenario:"):
            close_scenario()
            scenario_line, scenario_has_proof = (n, False) if section in ("ADDED", "MODIFIED") else (0, True)
        elif scenario_line and "**Proof:**" in line:
            scenario_has_proof = True
    close_scenario()


def lint_change(repo: Path, change: str, prefix: str) -> list[str]:
    errors: list[str] = []
    folder = repo / "openspec" / "changes" / change
    base = f"openspec/changes/{change}"
    if not folder.is_dir():
        return [f"{base}: no such change"]
    proposal = folder / "proposal.md"
    if not proposal.is_file():
        return [f"{base}/proposal.md: missing"]
    text = proposal.read_text(encoding="utf-8")
    size_match = SIZE_RE.search(text)
    size = size_match.group(1) if size_match else ""
    if not size:
        errors.append(f"{base}/proposal.md: first line must be '**Size:** S|M|L'")
    found = headings(text)
    design = folder / "design.md"
    design_found = headings(design.read_text(encoding="utf-8")) if design.is_file() else set()
    required = ["why", "what changes", "not to add"] + (["prior art and reuse"] if size in ("M", "L") else [])
    for name in required:
        if name not in found:
            errors.append(f"{base}/proposal.md: missing section '## {name.title()}'")
    if size == "L" and not design.is_file():
        errors.append(f"{base}/design.md: required for size L")
    if size in ("M", "L") and "change impact" not in found | design_found:
        errors.append(f"{base}: size {size} needs a '## Change impact' section (proposal or design)")
    tasks = folder / "tasks.md"
    if not tasks.is_file():
        errors.append(f"{base}/tasks.md: missing")
    else:
        n_tasks = 0
        for n, line in enumerate(tasks.read_text(encoding="utf-8").splitlines(), 1):
            match = TASK_RE.match(line)
            if match:
                n_tasks += 1
                body = match.group(1).lower()
                if "proof:" not in body:
                    errors.append(f"{base}/tasks.md:{n}: task without '— proof: `<command>`'")
                if "test first:" not in body:
                    errors.append(f"{base}/tasks.md:{n}: task without '— test first: <test or n/a>'")
        if not n_tasks:
            errors.append(f"{base}/tasks.md: no checkbox tasks")
    for spec in sorted((folder / "specs").rglob("spec.md")) if (folder / "specs").is_dir() else []:
        lint_specs(spec, spec.relative_to(repo).as_posix(), prefix, errors)
    for path in sorted(folder.rglob("*.md")):
        for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if TODO_RE.search(line):
                errors.append(f"{path.relative_to(repo).as_posix()}:{n}: TODO left in the change")
    return errors


def cmd_lint(repo: Path, changes: list[str]) -> list[str]:
    state = read_state(repo)
    if state.process != "ai-specs":
        raise AiSpecsError(f"{repo} does not run ai-specs ({state.reason or state.process})")
    errors: list[str] = []
    if version_tuple(state.version) >= (0, 2, 0):
        errors += approval.roles_errors(repo)
        errors += contracts.released_changes(repo)
    for change in changes or state.changes:
        errors += lint_change(repo, change, state.prefix)
    return errors


def version_tuple(text: str) -> tuple[int, ...]:
    try:
        return tuple(int(x) for x in text.split("."))
    except ValueError:
        return (0,)


# ---------------------------------------------------------------- doctor
def cmd_doctor(repo: Path) -> dict:
    state = read_state(repo)
    report = {"repo": repo.as_posix(), "process": state.process, "reason": state.reason,
              "kit_version": VERSION, "repo_kit_version": state.version, "prefix": state.prefix,
              "openspec": openspec_command(repo), "changes": {}}
    if state.process == "ai-specs":
        for change in state.changes:
            report["changes"][change] = lint_change(repo, change, state.prefix)
        report["kit_outdated"] = state.version != VERSION
    return report


# ---------------------------------------------------------------- cli
def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="ai_specs.py", description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("init")
    p.add_argument("repo", type=Path)
    p.add_argument("--prefix", required=True)
    p.add_argument("--project")
    p.add_argument("--language", default="English")
    p.add_argument("--owner", help="GitHub login written to openspec/roles.yaml when it does not exist yet")
    p.add_argument("--gate", help="the repo's single gate command, run by the CI gate job")
    p.add_argument("--kit-repo", help="<owner>/<repo> of ai-specs for the CI checkout (default: this kit's origin)")
    p.add_argument("--platform", action="store_true", help="a product platform repo: catalog, contracts, ADRs")
    p.add_argument("--product", help="product id for the platform catalog (default: repo name without -platform)")
    p = sub.add_parser("scaffold")
    p.add_argument("repo", type=Path)
    p.add_argument("change")
    p.add_argument("--size", required=True, choices=SIZES)
    p.add_argument("--capability")
    p = sub.add_parser("lint")
    p.add_argument("repo", type=Path)
    p.add_argument("changes", nargs="*")
    p = sub.add_parser("doctor")
    p.add_argument("repo", type=Path)
    p.add_argument("--json", action="store_true")
    p = sub.add_parser("contract")
    p.add_argument("action", choices=("new", "check"))
    p.add_argument("repo", type=Path)
    p.add_argument("name", nargs="?")
    p.add_argument("--kind", choices=("jsonschema", "openapi"), default="jsonschema")
    p = sub.add_parser("catalog")
    p.add_argument("action", choices=("check",))
    p.add_argument("repo", type=Path)
    p = sub.add_parser("impact")
    p.add_argument("repo", type=Path)
    p.add_argument("target")
    p = sub.add_parser("adr")
    p.add_argument("action", choices=("new",))
    p.add_argument("repo", type=Path)
    p.add_argument("title")
    p = sub.add_parser("digest")
    p.add_argument("repo", type=Path)
    p.add_argument("change")
    p = sub.add_parser("approve")
    p.add_argument("repo", type=Path)
    p.add_argument("issue", type=int)
    p = sub.add_parser("check-approval")
    p.add_argument("repo", type=Path)
    p.add_argument("issue", type=int, nargs="?")
    p.add_argument("--pr", type=int)
    args = ap.parse_args(argv)
    repo = args.repo.resolve()
    if not repo.is_dir():
        print(f"not a folder: {repo}", file=sys.stderr)
        return 2
    try:
        if args.cmd == "init":
            for item in cmd_init(repo, args.prefix, args.project or repo.name, args.language, args.owner,
                                 args.gate, args.kit_repo, args.platform, args.product):
                print(f"[ok] {item}")
            print(f"next: {openspec_command(repo)} validate --all --strict")
        elif args.cmd == "scaffold":
            for item in cmd_scaffold(repo, args.change, args.size, args.capability):
                print(f"[ok] {item}")
        elif args.cmd == "contract" and args.action == "new":
            if not args.name:
                print("contract new needs a name", file=sys.stderr)
                return 2
            for item in contracts.new(repo, args.name, args.kind):
                print(f"[ok] {item}")
        elif args.cmd == "contract":
            problems = contracts.check(repo)
            for problem in problems:
                print("ERROR", problem)
            print(f"{len(contracts.versions(repo))} contract version(s), {len(problems)} problem(s)")
            return 1 if problems else 0
        elif args.cmd == "catalog":
            problems = catalog.check(repo)
            for problem in problems:
                print("ERROR", problem)
            print(f"{len(problems)} problem(s)")
            return 1 if problems else 0
        elif args.cmd == "impact":
            found = catalog.impact(repo, args.target)
            if not found:
                print(f"nothing in the catalog references '{args.target}'")
            for kind, items in found.items():
                print(f"{kind}:")
                for item in items:
                    print(f"  - {item}")
        elif args.cmd == "adr":
            print(f"[ok] {cmd_adr(repo, args.title).relative_to(repo)}")
        elif args.cmd == "digest":
            print(approval.digest(approval.change_folder(repo, args.change)))
        elif args.cmd == "approve":
            approval.approve(repo, args.issue)
        elif args.cmd == "check-approval":
            if (args.issue is None) == (args.pr is None):
                print("give an issue number or --pr <n>", file=sys.stderr)
                return 2
            number = args.issue if args.issue is not None else approval.issue_of_pr(repo, args.pr)
            print(approval.check(repo, number))
        elif args.cmd == "lint":
            errors = cmd_lint(repo, args.changes)
            for error in errors:
                print("ERROR", error)
            print(f"{len(errors)} errors")
            return 1 if errors else 0
        else:
            report = cmd_doctor(repo)
            if args.json:
                print(json.dumps(report, indent=2))
            else:
                print(f"repo:     {report['repo']}")
                print(f"process:  {report['process']}" + (f" ({report['reason']})" if report["reason"] else ""))
                if report["process"] == "ai-specs":
                    outdated = " (outdated: re-run init)" if report["kit_outdated"] else ""
                    print(f"kit:      {report['repo_kit_version']} (current {VERSION}){outdated} · prefix {report['prefix']}")
                print(f"openspec: {report['openspec']}")
                for change, errors in report["changes"].items():
                    print(f"change:   {change}: {'ok' if not errors else f'{len(errors)} lint errors'}")
    except AiSpecsError as exc:
        print(f"ai-specs: {exc}", file=sys.stderr)
        return 1
    except approval.ApprovalError as exc:
        print(f"ai-specs: {exc}", file=sys.stderr)
        return exc.code
    except approval.ghcli.GhError as exc:
        print(f"ai-specs: {exc}", file=sys.stderr)
        return 2
    except contracts.ContractError as exc:
        print(f"ai-specs: {exc}", file=sys.stderr)
        return exc.code
    except catalog.CatalogError as exc:
        print(f"ai-specs: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
