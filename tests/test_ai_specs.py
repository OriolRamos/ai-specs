"""Tests for the ai-specs CLI: init, scaffold, lint and doctor on throwaway repos.

Run: python3 -m unittest discover -s tests
"""
from __future__ import annotations

import io
import json
import re
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest import mock

KIT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(KIT / "scripts"))

import ai_specs  # noqa: E402
import kitclone  # noqa: E402

kitclone.install()  # init pins the kit to the commit of tag v<VERSION>: use a tagged copy

GOOD_SPEC = """## Purpose

Greets every caller by name so all clients show the same predictable text.

## ADDED Requirements

### Requirement: LB-001 — Greeting by name
The service SHALL return a greeting that contains the caller's name.

#### Scenario: Named greeting
- **GIVEN** a caller named Ada
- **WHEN** it calls `GET /greet?name=Ada`
- **THEN** the response is `200` with body `{"text": "Hello, Ada"}`
- **Proof:** `pytest tests/test_greet.py::test_named` passes
"""

GOOD_TASKS = """## 1. Greeting
- [ ] 1.1 Greeting endpoint — test first: `tests/test_greet.py::test_named` — proof: `pytest -q tests/test_greet.py`
"""


def run(*argv: str) -> tuple[int, str]:
    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        code = ai_specs.main(list(argv))
    return code, out.getvalue() + err.getvalue()


class RepoTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.repo = Path(self._tmp.name) / "demo"
        self.repo.mkdir()
        (self.repo / "AGENTS.md").write_text("# Demo\n\nOwn rules.\n", encoding="utf-8")

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def init(self) -> None:
        code, out = run("init", str(self.repo), "--prefix", "LB", "--owner", "owner1", "--kit-repo", "o/ai-specs")
        self.assertEqual(code, 0, out)

    def fill(self, change: str = "add-greeting", size: str = "S") -> Path:
        self.assertEqual(run("scaffold", str(self.repo), change, "--size", size, "--capability", "greeting")[0], 0)
        folder = self.repo / "openspec" / "changes" / change
        proposal = (f"**Size:** {size}\n\n## Why\nCallers need a greeting.\n\n## What Changes\n- Add `GET /greet`.\n"
                    "- **Excludes:** localisation.\n\n## Not to add\n- No auth, no new config options.\n")
        if size in ("M", "L"):
            proposal += "\n## Prior art and reuse\n- Reuse the existing router.\n"
        if size == "M":
            proposal += "\n## Change impact\n| Changed | Used by | Breaks? | Rollback |\n|---|---|---|---|\n| router | app | no | revert |\n"
        (folder / "proposal.md").write_text(proposal, encoding="utf-8")
        (folder / "tasks.md").write_text(GOOD_TASKS, encoding="utf-8")
        (folder / "specs" / "greeting" / "spec.md").write_text(GOOD_SPEC, encoding="utf-8")
        return folder


class InitTest(RepoTest):
    def test_init_writes_config_folders_and_one_managed_block(self) -> None:
        self.init()
        self.init()  # idempotent
        config = (self.repo / "openspec" / "config.yaml").read_text(encoding="utf-8")
        self.assertIn("prefix=LB", config)
        self.assertNotIn("{{", config)
        self.assertTrue((self.repo / "openspec" / "specs").is_dir())
        agents = (self.repo / "AGENTS.md").read_text(encoding="utf-8")
        self.assertIn("Own rules.", agents)
        self.assertEqual(agents.count("ai-specs:begin"), 1)
        self.assertIn("LB-NNN", agents)

    def test_refuses_a_repo_with_another_process(self) -> None:
        (self.repo / "openspec").mkdir()
        (self.repo / "openspec" / "config.yaml").write_text("schema: spec-driven\n", encoding="utf-8")
        code, out = run("init", str(self.repo), "--prefix", "LB", "--owner", "owner1")
        self.assertEqual(code, 1)
        self.assertIn("not written by ai-specs", out)
        self.assertEqual((self.repo / "openspec" / "config.yaml").read_text(encoding="utf-8"), "schema: spec-driven\n")

    def test_refuses_an_azure_devops_repo_and_a_prefix_change(self) -> None:
        (self.repo / ".agents" / "skills" / "azure-devops").mkdir(parents=True)
        self.assertEqual(run("init", str(self.repo), "--prefix", "LB", "--owner", "owner1")[0], 1)
        (self.repo / ".agents" / "skills" / "azure-devops").rmdir()
        self.init()
        code, out = run("init", str(self.repo), "--prefix", "XY", "--owner", "owner1")
        self.assertEqual(code, 1)
        self.assertIn("never change", out)

    def test_every_rule_is_a_quoted_yaml_scalar(self) -> None:
        # OpenSpec silently ignores the whole config when YAML fails to parse (e.g. "test first: x" unquoted).
        for line in (KIT / "kit" / "config.yaml.tmpl").read_text(encoding="utf-8").splitlines():
            if line.startswith("    - "):
                self.assertTrue(line.startswith("    - '") and line.endswith("'") and line[7:-1].count("'") == 0, line)

    def test_bad_prefix(self) -> None:
        self.assertEqual(run("init", str(self.repo), "--prefix", "lb")[0], 1)


class LintTest(RepoTest):
    def setUp(self) -> None:
        super().setUp()
        self.init()

    def test_fresh_scaffold_fails_until_filled(self) -> None:
        run("scaffold", str(self.repo), "add-greeting", "--size", "L", "--capability", "greeting")
        code, out = run("lint", str(self.repo))
        self.assertEqual(code, 1)
        self.assertIn("TODO left", out)

    def test_filled_changes_of_every_size_pass(self) -> None:
        for size in ("S", "M"):
            self.fill(f"change-{size.lower()}", size)
        folder = self.fill("change-l", "L")
        (folder / "design.md").write_text("## Decisions\nKeep it small.\n\n## Change impact\n| a | b | c | d |\n",
                                          encoding="utf-8")
        code, out = run("lint", str(self.repo))
        self.assertEqual(code, 0, out)

    def test_each_rule_is_reported(self) -> None:
        folder = self.fill(size="M")
        (folder / "proposal.md").write_text("## Why\nx\n\n## What Changes\n- y\n", encoding="utf-8")
        (folder / "tasks.md").write_text("- [ ] 1.1 Do it\n", encoding="utf-8")
        (folder / "specs" / "greeting" / "spec.md").write_text(
            GOOD_SPEC.replace("LB-001", "XX-001").replace("- **Proof:** `pytest tests/test_greet.py::test_named` passes\n", ""),
            encoding="utf-8")
        code, out = run("lint", str(self.repo), "add-greeting")
        self.assertEqual(code, 1)
        for expected in ("Size:", "Not To Add", "without '— proof", "without '— test first",
                         "needs an id like LB-001", "without a '- **Proof:**'"):
            self.assertIn(expected, out)

    def test_removed_requirements_need_no_proof(self) -> None:
        folder = self.fill()
        (folder / "specs" / "greeting" / "spec.md").write_text(
            "## REMOVED Requirements\n\n### Requirement: Old thing\n**Reason**: gone\n**Migration**: none\n",
            encoding="utf-8")
        self.assertEqual(run("lint", str(self.repo))[0], 0)

    def test_scaffold_never_overwrites(self) -> None:
        folder = self.fill()
        before = (folder / "proposal.md").read_text(encoding="utf-8")
        run("scaffold", str(self.repo), "add-greeting", "--size", "L")
        self.assertEqual((folder / "proposal.md").read_text(encoding="utf-8"), before)


class DoctorTest(RepoTest):
    def test_reports_process_and_changes(self) -> None:
        code, out = run("doctor", str(self.repo))
        self.assertEqual(code, 0)
        self.assertIn("process:  none", out)
        self.init()
        self.fill()
        report = ai_specs.cmd_doctor(self.repo)
        self.assertEqual((report["process"], report["prefix"], report["kit_outdated"]), ("ai-specs", "LB", False))
        self.assertEqual(report["changes"], {"add-greeting": []})


if __name__ == "__main__":
    unittest.main()


class WorkflowTest(RepoTest):
    def test_workflow_has_three_jobs_the_gate_and_least_privileges(self) -> None:
        code, out = run("init", str(self.repo), "--prefix", "LB", "--owner", "owner1", "--gate", "make verify",
                        "--kit-repo", "someone/ai-specs")
        self.assertEqual(code, 0, out)
        text = (self.repo / ".github" / "workflows" / "ai-specs.yml").read_text(encoding="utf-8")
        for job in ("  ai-specs:", "  approval:", "  gate:"):
            self.assertIn(job, text)
        self.assertIn("        run: |\n          make verify\n", text)
        perms = text.split("permissions:\n", 1)[1].split("\n\n", 1)[0]
        self.assertEqual(sorted(line.strip() for line in perms.splitlines()),
                         ["contents: read", "issues: read", "pull-requests: read"])
        self.assertIn("repository: someone/ai-specs", text)
        self.assertIn(f"ref: {ai_specs.kit_commit()} # v{ai_specs.VERSION}", text)
        self.assertIn("check-approval . --pr", text)
        self.assertNotRegex(text, r"\{\{[A-Z_]+\}\}")  # every kit placeholder replaced (GitHub's ${{ }} stays)
        run("init", str(self.repo), "--prefix", "LB", "--kit-repo", "someone/ai-specs")  # gate kept on re-init
        self.assertIn("make verify", (self.repo / ".github" / "workflows" / "ai-specs.yml").read_text(encoding="utf-8"))

    def test_dependency_bots_skip_only_approval(self) -> None:
        run("init", str(self.repo), "--prefix", "LB", "--owner", "o1", "--kit-repo", "o/ai-specs", "--gate", "true")
        text = (self.repo / ".github" / "workflows" / "ai-specs.yml").read_text(encoding="utf-8")
        approval = text.split("  approval:", 1)[1].split("\n  gate:", 1)[0]
        for bot in ("dependabot[bot]", "renovate[bot]"):
            self.assertIn(f"github.event.pull_request.user.login != '{bot}'", approval)
            self.assertEqual(text.count(bot), 1)  # only in the approval job
        self.assertNotIn("user.login", text.split("  approval:", 1)[0])

    def test_without_a_gate_the_gate_job_fails_loudly(self) -> None:
        run("init", str(self.repo), "--prefix", "LB", "--owner", "owner1", "--kit-repo", "someone/ai-specs")
        text = (self.repo / ".github" / "workflows" / "ai-specs.yml").read_text(encoding="utf-8")
        self.assertIn("Declare this repo", text)
        self.assertIn("exit 1", text)




SHA_USES_RE = re.compile(r"^\s*(?:- )?uses: [A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+@[0-9a-f]{40} # v\d+(?:\.\d+)*$")


def run_scripts(text: str) -> list[str]:
    """The text of every `run:` step (single line or block scalar)."""
    scripts, lines = [], text.splitlines()
    for i, line in enumerate(lines):
        match = re.match(r"^(\s*)(?:- )?run:\s*(.*)$", line)
        if not match:
            continue
        if match.group(2) in ("|", ">", "|-", ">-"):
            indent, body = len(match.group(1)), []
            for nxt in lines[i + 1:]:
                if nxt.strip() and len(nxt) - len(nxt.lstrip()) <= indent:
                    break
                body.append(nxt)
            scripts.append("\n".join(body))
        else:
            scripts.append(match.group(2))
    return scripts


def job(text: str, name: str) -> str:
    return text.split(f"\n  {name}:\n", 1)[1].split("\n\n  ", 1)[0]


class CardWorkflowTest(RepoTest):
    """ASP-116, ASP-119: kit 0.3.0 writes the card workflow, least-privilege and pinned."""

    def card_workflow(self) -> str:
        return (self.repo / ".github" / "workflows" / "ai-specs-approval.yml").read_text(encoding="utf-8")

    def test_template_audit(self) -> None:
        self.init()
        text = self.card_workflow()
        self.assertTrue(text.startswith(f"# ai-specs:workflow version={ai_specs.VERSION}\n"))
        perms = text.split("\npermissions:\n", 1)[1].split("\n\n", 1)[0]
        self.assertEqual(sorted(line.strip() for line in perms.splitlines()), ["contents: read", "issues: write"])
        self.assertEqual(text.count("permissions:"), 1)  # no job widens it
        uses = [line for line in text.splitlines() if "uses:" in line]
        self.assertTrue(uses)
        for line in uses:
            self.assertRegex(line, SHA_USES_RE)
        for script in run_scripts(text):
            self.assertNotIn("${{", script)  # values reach scripts only through env and the event file
        self.assertNotIn("secrets.", text)
        sha = ai_specs.kit_commit()
        self.assertRegex(sha, r"^[0-9a-f]{40}$")
        self.assertEqual(text.count(f"ref: {sha} # v{ai_specs.VERSION}"), 2)
        self.assertEqual(text.count("persist-credentials: false"), 6)
        self.assertNotRegex(text, r"\{\{[A-Z_]+\}\}")

    def test_job_conditions_and_concurrency(self) -> None:
        self.init()
        text = self.card_workflow()
        render, review = job(text, "render"), job(text, "review")
        self.assertIn("github.event_name == 'issues' && contains(github.event.issue.labels.*.name, 'type:change')",
                      render)
        self.assertIn("github.event_name == 'push' && !github.event.deleted", render)
        self.assertIn("cancel-in-progress: true", render)
        for condition in ("github.event_name == 'issue_comment'", "!github.event.issue.pull_request",
                          "github.event.comment.user.login == 'github-actions[bot]'",
                          "startsWith(github.event.comment.body, '<!-- ai-specs:approval-card ')",
                          "github.event.sender.type != 'Bot'"):
            self.assertIn(condition, review)
        self.assertNotIn("concurrency:", review)
        self.assertIn("card render . --event \"$GITHUB_EVENT_PATH\" --src change-src", render)
        self.assertIn("card review . --event \"$GITHUB_EVENT_PATH\" --src change-src", review)
        for part in (render, review):
            self.assertIn("ref: ${{ github.event.repository.default_branch }}", part)  # roles from the default branch
            self.assertIn("ref: ${{ steps.resolve.outputs.branch }}\n          path: change-src", part)
        self.assertIn("types: [edited]", text.split("issue_comment:", 1)[1].split("\n  push:", 1)[0])

    def test_kit_workflow_pins_and_actions_read(self) -> None:
        self.init()
        text = (self.repo / ".github" / "workflows" / "ai-specs.yml").read_text(encoding="utf-8")
        for line in (line for line in text.splitlines() if "uses:" in line):
            self.assertRegex(line, SHA_USES_RE)
        approval_job = job(text, "approval")
        perms = approval_job.split("permissions:", 1)[1].split("\n    env:", 1)[0]
        self.assertEqual(sorted(line.strip() for line in perms.splitlines()[1:]),
                         ["actions: read", "contents: read", "issues: read", "pull-requests: read"])
        self.assertNotIn("actions:", text.split("\njobs:", 1)[0])
        self.assertNotIn("write", text)

    def test_init_upgrades_and_doctor_reports(self) -> None:
        code, out = run("init", str(self.repo), "--prefix", "EE", "--owner", "owner1", "--kit-repo", "o/ai-specs",
                        "--gate", "make verify")
        self.assertEqual(code, 0, out)
        workflows = self.repo / ".github" / "workflows"
        # make it look like a kit 0.2.2 repo: old markers, no card workflow
        config = self.repo / "openspec" / "config.yaml"
        config.write_text(config.read_text(encoding="utf-8").replace(f"version={ai_specs.VERSION}", "version=0.2.2"),
                          encoding="utf-8")
        old = workflows / "ai-specs.yml"
        old.write_text(old.read_text(encoding="utf-8").replace(f"version={ai_specs.VERSION}", "version=0.2.2"),
                       encoding="utf-8")
        (workflows / "ai-specs-approval.yml").unlink()
        report = ai_specs.cmd_doctor(self.repo)
        self.assertEqual((report["kit_outdated"], report["card_workflow"]), (True, "missing"))
        self.assertIn("card:     .github/workflows/ai-specs-approval.yml: missing (re-run init)",
                      run("doctor", str(self.repo))[1])
        code, out = run("init", str(self.repo), "--prefix", "EE", "--kit-repo", "o/ai-specs")
        self.assertEqual(code, 0, out)
        for name in ("ai-specs.yml", "ai-specs-approval.yml"):
            self.assertTrue((workflows / name).read_text(encoding="utf-8").startswith(
                f"# ai-specs:workflow version={ai_specs.VERSION}\n"), name)
        text = old.read_text(encoding="utf-8")
        self.assertIn("make verify", text)
        self.assertIn("actions: read", job(text, "approval"))
        report = ai_specs.cmd_doctor(self.repo)
        self.assertEqual((report["kit_outdated"], report["card_workflow"]), (False, "ok"))
        card_file = workflows / "ai-specs-approval.yml"
        card_file.write_text(card_file.read_text(encoding="utf-8").replace(f"version={ai_specs.VERSION}",
                                                                           "version=0.2.9"), encoding="utf-8")
        self.assertEqual(ai_specs.cmd_doctor(self.repo)["card_workflow"], "outdated (0.2.9)")

    def test_init_refuses_without_tag(self) -> None:
        untagged = kitclone.copy_kit(tagged=False)
        with mock.patch.object(ai_specs, "KIT", untagged):
            code, out = run("init", str(self.repo), "--prefix", "EE", "--owner", "owner1", "--kit-repo", "o/ai-specs")
        self.assertNotEqual(code, 0)
        self.assertIn(f"tag v{ai_specs.VERSION} not found in the kit: fetch tags", out)
        self.assertFalse((self.repo / ".github").exists())
        self.assertFalse((self.repo / "openspec").exists())

    def test_self_mode(self) -> None:
        kit = kitclone.copy_kit(tagged=False, fresh=True)  # the kit repo itself needs no tag
        (kit / "openspec").mkdir()
        (kit / "openspec" / "roles.yaml").write_text("approvers: [owner1]\nmin_approvals: 1\n", encoding="utf-8")
        (kit / "CLAUDE.md").write_text("# kit\n", encoding="utf-8")
        with mock.patch.object(ai_specs, "KIT", kit):
            code, out = run("init", str(kit), "--prefix", "ASP", "--gate", "true")
        self.assertEqual(code, 0, out)
        for name in ("ai-specs.yml", "ai-specs-approval.yml"):
            text = (kit / ".github" / "workflows" / name).read_text(encoding="utf-8")
            self.assertNotIn(".ai-specs-kit", text, name)
            self.assertNotIn("kit-checkout", text, name)
            self.assertNotIn("repository:", text, name)
            for line in (line for line in text.splitlines() if "uses:" in line):
                self.assertRegex(line, SHA_USES_RE)
        card_text = (kit / ".github" / "workflows" / "ai-specs-approval.yml").read_text(encoding="utf-8")
        self.assertIn("python3 scripts/ai_specs.py card review .", card_text)
        self.assertEqual(card_text.count("python3 scripts/ai_specs.py card resolve ."), 2)


class CardCliTest(unittest.TestCase):
    """`ai_specs.py card resolve|render|review . --event <file>`: exit codes and GITHUB_OUTPUT (task 3.4)."""

    def setUp(self) -> None:
        sys.path.insert(0, str(KIT / "tests"))
        import test_card  # noqa: PLC0415  (the card fixture: a git branch and a fake gh)

        self.fixture = test_card.ReviewTest("run")
        self.fixture.setUp()
        self.addCleanup(self.fixture.tearDown)
        self.tmp = Path(self.fixture._tmp.name)
        self.output = self.tmp / "github_output"
        self.output.write_text("", encoding="utf-8")
        self.event = self.tmp / "event.json"

    def card(self, action: str, event: dict, **env: str) -> tuple[int, str]:
        self.event.write_text(json.dumps(event), encoding="utf-8")
        values = {"GITHUB_OUTPUT": str(self.output), **env}
        with mock.patch.dict(os.environ, values):
            if "GITHUB_RUN_ID" not in env:
                os.environ.pop("GITHUB_RUN_ID", None)
            return run("card", action, str(self.fixture.base), "--event", str(self.event),
                       "--src", str(self.fixture.src))

    def test_resolve_writes_outputs(self) -> None:
        code, out = self.card("resolve", self.fixture.push_event())
        self.assertEqual(code, 0, out)
        self.assertEqual(self.output.read_text(encoding="utf-8"),
                         "proceed=true\nissue=12\nchange=demo\nbranch=change/12-demo\n")
        self.output.write_text("", encoding="utf-8")
        code, out = self.card("resolve", self.fixture.push_event("refs/heads/feature/x"))
        self.assertEqual(code, 0, out)
        self.assertEqual(self.output.read_text(encoding="utf-8"), "proceed=false\n")
        self.assertIn("notice:", out)

    def test_render_then_review(self) -> None:
        self.assertEqual(self.card("render", self.fixture.push_event())[0], 0)
        self.assertEqual(len(self.fixture.cards()), 1)
        target = self.fixture.cards()[0]
        event = self.fixture.issue_event()
        event["comment"] = {"id": target["id"], "body": target["body"].replace("- [ ]", "- [x]", 1),
                            "user": {"login": "github-actions[bot]", "type": "Bot"}}
        event["sender"] = {"login": "someone", "type": "User"}
        code, out = self.card("review", event, GITHUB_RUN_ID="77")
        self.assertEqual(code, 1, out)
        self.assertIn("not an approver", out)
        event["sender"] = {"login": "owner", "type": "User"}
        self.assertEqual(self.card("review", event)[0], 2)  # no run id: not inside the workflow
        self.fixture.run_record("77", "owner")
        code, out = self.card("review", event, GITHUB_RUN_ID="77")
        self.assertEqual(code, 0, out)
        self.assertEqual(len(self.fixture.records()), 1)

    def test_github_failure_is_exit_2(self) -> None:
        self.fixture.state["offline"] = True
        self.fixture.save()
        self.assertEqual(self.card("render", self.fixture.push_event())[0], 2)
        self.assertEqual(self.card("resolve", self.fixture.push_event())[0], 2)


class AdrTest(RepoTest):
    def test_numbered_adrs_from_the_template(self) -> None:
        code, out = run("adr", "new", str(self.repo), "Use develop as default branch")
        self.assertEqual(code, 0, out)
        first = self.repo / "docs" / "adr" / "0001-use-develop-as-default-branch.md"
        text = first.read_text(encoding="utf-8")
        for section in ("**Status:**", "## Context", "## Decision", "## Consequences"):
            self.assertIn(section, text)
        run("adr", "new", str(self.repo), "Second one")
        self.assertTrue((self.repo / "docs" / "adr" / "0002-second-one.md").is_file())


class CompatibilityTest(RepoTest):
    def test_a_kit_01_repo_without_roles_still_lints_clean(self) -> None:
        self.init()
        config = self.repo / "openspec" / "config.yaml"
        config.write_text(config.read_text(encoding="utf-8").replace(f"version={ai_specs.VERSION}", "version=0.1.0"),
                          encoding="utf-8")
        (self.repo / "openspec" / "roles.yaml").unlink()
        self.assertEqual(ai_specs.cmd_lint(self.repo, []), [])

    def test_a_kit_02_repo_needs_roles(self) -> None:
        self.init()
        (self.repo / "openspec" / "roles.yaml").unlink()
        self.assertTrue(any("roles.yaml is missing" in e for e in ai_specs.cmd_lint(self.repo, [])))


class PurposeTest(RepoTest):
    def setUp(self) -> None:
        super().setUp()
        self.init()

    def test_new_capability_needs_a_long_enough_purpose(self) -> None:
        folder = self.fill()
        spec = folder / "specs" / "greeting" / "spec.md"
        text = spec.read_text(encoding="utf-8")
        spec.write_text("## ADDED" + text.split("## ADDED", 1)[1], encoding="utf-8")
        errors = ai_specs.cmd_lint(self.repo, [])
        self.assertTrue(any("new capability needs a ## Purpose of at least 50 characters" in e for e in errors), errors)
        spec.write_text("## Purpose\n\nToo short.\n\n" + spec.read_text(encoding="utf-8"), encoding="utf-8")
        self.assertTrue(any("## Purpose" in e for e in ai_specs.cmd_lint(self.repo, [])))

    def test_existing_capability_needs_no_purpose(self) -> None:
        folder = self.fill()
        living = self.repo / "openspec" / "specs" / "greeting"
        living.mkdir(parents=True)
        (living / "spec.md").write_text("# greeting\n", encoding="utf-8")
        spec = folder / "specs" / "greeting" / "spec.md"
        spec.write_text("## ADDED" + spec.read_text(encoding="utf-8").split("## ADDED", 1)[1], encoding="utf-8")
        self.assertEqual(ai_specs.cmd_lint(self.repo, []), [])

    def test_scaffold_template_carries_a_purpose(self) -> None:
        run("scaffold", str(self.repo), "x-y", "--size", "S", "--capability", "cap")
        self.assertTrue((self.repo / "openspec/changes/x-y/specs/cap/spec.md").read_text().startswith("## Purpose"))


class StandardMemoryTest(unittest.TestCase):
    """ASP-073: the standard's memory section carries the taxonomy with the brain and the linking rule."""

    def setUp(self) -> None:
        text = (KIT / "docs" / "standard.md").read_text(encoding="utf-8")
        self.assertIn("\n## 13. Memory\n", text)
        self.section = text.split("\n## 13. Memory\n", 1)[1].split("\n## ", 1)[0]

    def test_taxonomy_table_has_the_brain_row(self) -> None:
        header = "| Knowledge | Canonical place | In the brain |"
        self.assertIn(header, self.section)
        rows = [line for line in self.section.splitlines() if line.startswith("| ")]
        brain_rows = [r for r in rows if r.split("|")[2].strip() == "**brain**"]
        self.assertEqual(len(brain_rows), 1, rows)
        for kind in ("Research", "attempts", "failures", "lessons"):
            self.assertIn(kind, brain_rows[0])
        for canonical in ("`openspec/specs/`", "`docs/adr/`", "issue"):
            self.assertTrue(any(canonical in r for r in rows), canonical)

    def test_links_does_not_define_rule(self) -> None:
        self.assertIn("ASP-073", self.section)
        self.assertIn("links, it does not define", self.section)
        self.assertIn("restates", self.section)

    def test_one_memory_per_machine(self) -> None:
        self.assertIn("one brain installation per machine", self.section)
        self.assertIn("nothing leaves the machine", self.section)
        self.assertIn("ai-brain", self.section)

    def test_lessons_rule_kept(self) -> None:
        self.assertIn("A lesson that repeats becomes a `type:change` issue", self.section)
