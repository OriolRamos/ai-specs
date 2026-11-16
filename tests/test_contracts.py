"""ASP-040 … ASP-042: contract skeleton, conformance through an injected validator runner, released immutability."""
from __future__ import annotations

import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

KIT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(KIT / "scripts"))
sys.path.insert(0, str(KIT / "tests"))

import ai_specs  # noqa: E402
import kitclone  # noqa: E402

kitclone.install()  # init pins the kit to the commit of tag v<VERSION>: use a tagged copy
import contracts  # noqa: E402


def fake_ajv(cmd: list[str], cwd: Path) -> tuple[int, str]:
    """A tiny stand-in for ajv: an example is valid when it is an object with a non-empty string 'id'."""
    data = json.loads(Path(cmd[cmd.index("-d") + 1]).read_text(encoding="utf-8"))
    ok = isinstance(data, dict) and isinstance(data.get("id"), str) and data["id"] and set(data) == {"id"}
    return (0, f"{cmd[cmd.index('-d') + 1]} valid") if ok else (1, f"{cmd[cmd.index('-d') + 1]} invalid")


class NewTest(unittest.TestCase):
    def test_jsonschema_and_openapi_skeletons(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            files = contracts.new(repo, "greeting", "jsonschema")
            self.assertIn("contracts/greeting/v1/schema.json", files)
            self.assertIn("contracts/greeting/v1/examples/invalid/missing-required.json", files)
            self.assertTrue((repo / "contracts/greeting/v1/README.md").is_file())
            contracts.new(repo, "health-api", "openapi")
            self.assertTrue((repo / "contracts/health-api/v1/openapi.yaml").is_file())
            with self.assertRaises(contracts.ContractError):
                contracts.new(repo, "greeting", "jsonschema")


class CheckTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.repo = Path(self._tmp.name)
        contracts.new(self.repo, "greeting", "jsonschema")
        self.v1 = self.repo / "contracts" / "greeting" / "v1"

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_skeleton_conforms(self) -> None:
        self.assertEqual(contracts.check(self.repo, fake_ajv), [])

    def test_invalid_example_that_passes_fails_the_check(self) -> None:
        (self.v1 / "examples" / "invalid" / "sneaky.json").write_text('{"id": "ok"}', encoding="utf-8")
        problems = contracts.check(self.repo, fake_ajv)
        self.assertEqual(len(problems), 1)
        self.assertIn("sneaky.json: invalid example accepted", problems[0])

    def test_rejected_valid_example_and_layout_problems(self) -> None:
        (self.v1 / "examples" / "valid" / "bad.json").write_text("{}", encoding="utf-8")
        (self.v1 / "openapi.yaml").write_text("openapi: 3.1.0\n", encoding="utf-8")
        problems = contracts.check(self.repo, fake_ajv)
        self.assertIn("exactly one of schema.json or openapi.yaml", problems[0])
        (self.v1 / "openapi.yaml").unlink()
        self.assertTrue(any("valid example rejected" in p for p in contracts.check(self.repo, fake_ajv)))

    def test_verdict_is_read_at_the_end_of_the_line_not_in_the_path(self) -> None:
        self.assertEqual(contracts._ajv_verdict("contracts/x/v1/examples/invalid/a.json valid\n"), "valid")
        self.assertEqual(contracts._ajv_verdict("contracts/x/v1/examples/valid/a.json invalid\n[{...}]\n"), "invalid")
        self.assertEqual(contracts._ajv_verdict("npm ERR! 404\n"), "")

    def test_validator_that_cannot_run_is_exit_2(self) -> None:
        with self.assertRaises(contracts.ContractError) as ctx:
            contracts.check(self.repo, lambda cmd, cwd: (127, "npx: command not found"))
        self.assertEqual(ctx.exception.code, 2)

    def test_pinned_validators_through_npx(self) -> None:
        calls: list[list[str]] = []
        contracts.check(self.repo, lambda cmd, cwd: calls.append(cmd) or fake_ajv(cmd, cwd))
        self.assertEqual(calls[0][:3], ["npx", "-y", contracts.AJV])
        with mock.patch.dict(os.environ, {"AI_SPECS_NPX": "/opt/runner"}):
            calls.clear()
            contracts.check(self.repo, lambda cmd, cwd: calls.append(cmd) or fake_ajv(cmd, cwd))
            self.assertEqual(calls[0][:2], ["/opt/runner", contracts.AJV])


def git(repo: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True,
                   env={**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@example.invalid",
                        "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@example.invalid"})


class ImmutableTest(unittest.TestCase):
    def test_edit_to_a_released_contract_fails_lint(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            with redirect_stdout(io.StringIO()):
                ai_specs.cmd_init(repo, "LB", "repo", "English", owner="o1", kit_repo="o/ai-specs")
            contracts.new(repo, "greeting", "jsonschema")
            git(repo, "init", "-q", "-b", "production")
            git(repo, "add", "-A")
            git(repo, "commit", "-q", "-m", "release")
            git(repo, "update-ref", "refs/remotes/origin/production", "HEAD")
            self.assertEqual(contracts.released_changes(repo), [])
            schema = repo / "contracts/greeting/v1/schema.json"
            schema.write_text(schema.read_text(encoding="utf-8").replace('"minLength": 1', '"minLength": 2'),
                              encoding="utf-8")
            errors = ai_specs.cmd_lint(repo, [])
            self.assertTrue(any("released contract greeting/v1 is immutable: create v2" in e for e in errors), errors)
            contracts.new(repo, "other", "jsonschema")  # not released yet: free to edit
            self.assertEqual(len(contracts.released_changes(repo)), 1)


if __name__ == "__main__":
    unittest.main()
