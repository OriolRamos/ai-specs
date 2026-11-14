"""Tests for the ai-specs CLI: init, scaffold, lint and doctor on throwaway repos.

Run: python3 -m unittest discover -s tests
"""
from __future__ import annotations

import io
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

KIT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(KIT / "scripts"))

import ai_specs  # noqa: E402

GOOD_SPEC = """## ADDED Requirements

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
        self.assertIn(f"ref: v{ai_specs.VERSION}", text)
        self.assertIn("check-approval . --pr", text)
        self.assertNotRegex(text, r"\{\{[A-Z_]+\}\}")  # every kit placeholder replaced (GitHub's ${{ }} stays)
        run("init", str(self.repo), "--prefix", "LB", "--kit-repo", "someone/ai-specs")  # gate kept on re-init
        self.assertIn("make verify", (self.repo / ".github" / "workflows" / "ai-specs.yml").read_text(encoding="utf-8"))

    def test_without_a_gate_the_gate_job_fails_loudly(self) -> None:
        run("init", str(self.repo), "--prefix", "LB", "--owner", "owner1", "--kit-repo", "someone/ai-specs")
        text = (self.repo / ".github" / "workflows" / "ai-specs.yml").read_text(encoding="utf-8")
        self.assertIn("Declare this repo", text)
        self.assertIn("exit 1", text)


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
