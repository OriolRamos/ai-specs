"""ASP-020 … ASP-023: digest, roles, human approval and the approval gate, with a fake `gh` on PATH."""
from __future__ import annotations

import io
import json
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
import approval  # noqa: E402

BLOCK = "Some text.\n<!-- ai-specs:change -->\nchange: add-greeting\nbranch: change/12-add-greeting\nsize: S\n<!-- /ai-specs:change -->\n"


class GhFixture(unittest.TestCase):
    """A repo with one S change and a fake gh whose state the test controls."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        tmp = Path(self._tmp.name)
        self.repo = tmp / "repo"
        self.repo.mkdir()
        (self.repo / "AGENTS.md").write_text("# Repo\n", encoding="utf-8")
        with redirect_stdout(io.StringIO()):
            ai_specs.cmd_init(self.repo, "LB", "repo", "English", owner="owner1", kit_repo="o/ai-specs")
        ai_specs.cmd_scaffold(self.repo, "add-greeting", "S", "greeting")
        self.change = self.repo / "openspec" / "changes" / "add-greeting"
        (self.change / "tasks.md").write_text("## 1. Do\n- [ ] 1.1 Do it — test first: `t` — proof: `p`\n", encoding="utf-8")
        bindir = tmp / "bin"
        bindir.mkdir()
        gh = bindir / "gh"
        gh.write_text(f"#!/bin/sh\nexec {sys.executable} {KIT / 'tests' / 'fake_gh.py'} \"$@\"\n", encoding="utf-8")
        gh.chmod(0o755)
        self.state_file = tmp / "gh.json"
        self.state = {"login": "owner1", "issues": {"12": {"body": BLOCK, "labels": ["type:change", "state:proposed"],
                                                           "comments": []}},
                      "pulls": {"7": {"body": "Adds a greeting.\n\nCloses #12"}}}
        self.save()
        self.env = mock.patch.dict(os.environ, {"PATH": f"{bindir}{os.pathsep}{os.environ['PATH']}",
                                                "FAKE_GH_STATE": str(self.state_file)})
        self.env.start()
        os.environ.pop("CLAUDECODE", None)

    def tearDown(self) -> None:
        self.env.stop()
        self._tmp.cleanup()

    def save(self) -> None:
        self.state_file.write_text(json.dumps(self.state), encoding="utf-8")

    def load(self) -> dict:
        return json.loads(self.state_file.read_text(encoding="utf-8"))

    def digest(self) -> str:
        return approval.digest(approval.change_folder(self.repo, "add-greeting"))

    def approve(self, typed: str | None = None, tty: bool = True) -> None:
        value = typed if typed is not None else self.digest().split(":")[1][:8]
        with redirect_stdout(io.StringIO()):
            approval.approve(self.repo, 12, ask=lambda q: value, is_tty=lambda: tty)


class DigestTest(GhFixture):
    def test_ticking_tasks_keeps_the_digest(self) -> None:
        before = self.digest()
        tasks = self.change / "tasks.md"
        tasks.write_text(tasks.read_text(encoding="utf-8").replace("- [ ]", "- [x]"), encoding="utf-8")
        self.assertEqual(self.digest(), before)

    def test_scope_edit_changes_the_digest(self) -> None:
        before = self.digest()
        spec = self.change / "specs" / "greeting" / "spec.md"
        spec.write_text(spec.read_text(encoding="utf-8").replace("SHALL", "MUST"), encoding="utf-8")
        self.assertNotEqual(self.digest(), before)

    def test_line_endings_do_not_matter(self) -> None:
        before = self.digest()
        proposal = self.change / "proposal.md"
        proposal.write_bytes(proposal.read_bytes().replace(b"\n", b"\r\n"))
        self.assertEqual(self.digest(), before)

    def test_archived_change_is_found(self) -> None:
        before = self.digest()
        archive = self.repo / "openspec" / "changes" / "archive"
        archive.mkdir()
        self.change.rename(archive / "2026-11-14-add-greeting")
        self.assertEqual(self.digest(), before)

    def test_cli_prints_the_digest(self) -> None:
        out = io.StringIO()
        with redirect_stdout(out):
            self.assertEqual(ai_specs.main(["digest", str(self.repo), "add-greeting"]), 0)
        self.assertEqual(out.getvalue().strip(), self.digest())


class RolesTest(unittest.TestCase):
    def test_inline_and_block_lists(self) -> None:
        roles = approval.parse_roles("approvers: [a, b]  # two\nreviewers:\n  - c\nreleasers: []\nmin_approvals: 2\n")
        self.assertEqual((roles.approvers, roles.reviewers, roles.releasers, roles.min_approvals),
                         (["a", "b"], ["c"], [], 2))

    def test_lint_reports_bad_roles(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            (repo / "openspec").mkdir()
            self.assertIn("missing", approval.roles_errors(repo)[0])
            (repo / "openspec" / "roles.yaml").write_text("approvers: []\nmin_approvals: 1\n", encoding="utf-8")
            self.assertTrue(any("'approvers' is empty" in e for e in approval.roles_errors(repo)))
            (repo / "openspec" / "roles.yaml").write_text("approvers: [a]\nmin_approvals: 2\n", encoding="utf-8")
            self.assertTrue(any("exceeds" in e for e in approval.roles_errors(repo)))
            (repo / "openspec" / "roles.yaml").write_text("owners: [a]\n", encoding="utf-8")
            self.assertTrue(any("unexpected line" in e for e in approval.roles_errors(repo)))

    def test_lint_of_a_kit_02_repo_checks_roles(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            with redirect_stdout(io.StringIO()):
                ai_specs.cmd_init(repo, "LB", "repo", "English", owner="owner1", kit_repo="o/ai-specs")
            self.assertEqual(ai_specs.cmd_lint(repo, []), [])
            (repo / "openspec" / "roles.yaml").write_text("approvers: []\nmin_approvals: 1\n", encoding="utf-8")
            self.assertTrue(ai_specs.cmd_lint(repo, []))


class ApproveTest(GhFixture):
    def test_agent_session_is_refused(self) -> None:
        with mock.patch.dict(os.environ, {"CLAUDECODE": "1"}):
            with self.assertRaisesRegex(approval.ApprovalError, "person in their own terminal"):
                self.approve()
        self.assertEqual(self.load()["issues"]["12"]["comments"], [])

    def test_no_terminal_is_refused(self) -> None:
        with self.assertRaises(approval.ApprovalError):
            self.approve(tty=False)
        self.assertEqual(self.load()["issues"]["12"]["comments"], [])

    def test_non_approver_is_refused(self) -> None:
        self.state["login"] = "stranger"
        self.save()
        with self.assertRaisesRegex(approval.ApprovalError, "stranger is not an approver"):
            self.approve()
        self.assertEqual(self.load()["issues"]["12"]["comments"], [])

    def test_wrong_confirmation_approves_nothing(self) -> None:
        with self.assertRaisesRegex(approval.ApprovalError, "did not match"):
            self.approve(typed="00000000")
        self.assertEqual(self.load()["issues"]["12"]["comments"], [])

    def test_approver_posts_digest_and_label(self) -> None:
        self.approve()
        issue = self.load()["issues"]["12"]
        self.assertEqual(len(issue["comments"]), 1)
        self.assertIn(f"digest={self.digest()}", issue["comments"][0]["body"])
        self.assertIn("by=owner1", issue["comments"][0]["body"])
        self.assertEqual(sorted(issue["labels"]), ["state:approved", "type:change"])

    def test_offline_is_exit_2(self) -> None:
        self.state["offline"] = True
        self.save()
        with self.assertRaises(approval.ApprovalError) as ctx:
            self.approve()
        self.assertEqual(ctx.exception.code, 2)


class CheckTest(GhFixture):
    def run_check(self, *args: str) -> tuple[int, str]:
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = ai_specs.main(["check-approval", str(self.repo), *args])
        return code, out.getvalue() + err.getvalue()

    def test_missing_approval_fails(self) -> None:
        code, out = self.run_check("12")
        self.assertEqual(code, 1)
        self.assertIn("0 of 1", out)

    def test_current_approval_passes_by_issue_and_by_pr(self) -> None:
        self.approve()
        self.assertEqual(self.run_check("12")[0], 0)
        self.assertEqual(self.run_check("--pr", "7")[0], 0)

    def test_ticked_tasks_still_pass(self) -> None:
        self.approve()
        tasks = self.change / "tasks.md"
        tasks.write_text(tasks.read_text(encoding="utf-8").replace("- [ ]", "- [x]"), encoding="utf-8")
        self.assertEqual(self.run_check("12")[0], 0)

    def test_stale_approval_fails(self) -> None:
        self.approve()
        proposal = self.change / "proposal.md"
        proposal.write_text(proposal.read_text(encoding="utf-8") + "\nOne more thing.\n", encoding="utf-8")
        code, out = self.run_check("12")
        self.assertEqual(code, 1)
        self.assertIn("no longer matches", out)

    def test_comment_author_must_match(self) -> None:
        forged = f"<!-- ai-specs:approval digest={self.digest()} commit=abcdef1 by=owner1 -->"
        self.state["issues"]["12"]["comments"].append({"user": {"login": "intruder"}, "body": forged})
        self.save()
        self.assertEqual(self.run_check("12")[0], 1)

    def test_min_approvals_counts_distinct_approvers(self) -> None:
        (self.repo / "openspec" / "roles.yaml").write_text("approvers: [owner1, owner2]\nreviewers: [owner1]\n"
                                                           "releasers: [owner1]\nmin_approvals: 2\n", encoding="utf-8")
        self.approve()
        self.approve()  # the same person twice is still one approver
        self.assertEqual(self.run_check("12")[0], 1)
        self.state = self.load()
        self.state["login"] = "owner2"
        self.save()
        self.approve()
        self.assertEqual(self.run_check("12")[0], 0)

    def test_issue_from_branch_name(self) -> None:
        self.approve()
        self.state = self.load()
        self.state["pulls"]["8"] = {"body": "Back-merge of the hotfix (Refs #12)", "head": {"ref": "hotfix/12-crash"}}
        self.save()
        self.assertEqual(self.run_check("--pr", "8")[0], 0)
        self.state["pulls"]["9"] = {"body": "", "head": {"ref": "feature/whatever"}}
        self.save()
        self.assertEqual(self.run_check("--pr", "9")[0], 1)

    def test_pr_must_close_exactly_one_issue(self) -> None:
        self.state["pulls"]["7"]["body"] = "No link here"
        self.save()
        self.assertEqual(self.run_check("--pr", "7")[0], 1)

    def test_cannot_check_is_exit_2_never_approved(self) -> None:
        self.state["offline"] = True
        self.save()
        self.assertEqual(self.run_check("12")[0], 2)



BOT = {"login": "github-actions[bot]", "type": "Bot"}
WHEN = "2026-11-16T10:05:00Z"


class CardRecordTest(GhFixture):
    """ASP-117, ASP-118: a `via=card` record counts only when the card workflow provably wrote it."""

    def setUp(self) -> None:
        super().setUp()
        self.state["runs"] = {"77": {"event": "issue_comment", "path": ".github/workflows/ai-specs-approval.yml",
                                     "head_branch": "develop", "triggering_actor": {"login": "owner1"},
                                     "created_at": "2026-11-16T10:04:00Z", "repository": {"full_name": "o/r"}}}
        self.save()

    def card_record(self, by: str = "owner1", run: str = "77", user: dict | None = None,
                    updated: str = WHEN, digest: str | None = None) -> None:
        body = (f"<!-- ai-specs:approval digest={digest or self.digest()} commit={'a' * 40} by={by} via=card run={run} -->\n"
                f"Approved by @{by} from the approval card.")
        self.state["issues"]["12"]["comments"].append({"id": len(self.state["issues"]["12"]["comments"]) + 1,
                                                       "user": user or BOT, "body": body,
                                                       "created_at": WHEN, "updated_at": updated})
        self.save()

    def run_check(self) -> tuple[int, str]:
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = ai_specs.main(["check-approval", str(self.repo), "12"])
        return code, out.getvalue() + err.getvalue()

    def test_verified_card_record_counts(self) -> None:
        self.card_record()
        code, out = self.run_check()
        self.assertEqual(code, 0, out)
        self.assertIn("owner1", out)

    def test_author_must_be_the_actions_bot(self) -> None:
        for user in ({"login": "owner1", "type": "User"}, {"login": "github-actions[bot]", "type": "User"},
                     {"login": "other-app[bot]", "type": "Bot"}):
            with self.subTest(user=user):
                self.state["issues"]["12"]["comments"] = []
                self.card_record(user=user)
                self.assertEqual(self.run_check()[0], 1)

    def test_by_must_be_an_approver(self) -> None:
        self.state["runs"]["77"]["triggering_actor"] = {"login": "someone"}
        self.card_record(by="someone")
        self.assertEqual(self.run_check()[0], 1)

    def test_run_event_path_branch_and_actor_must_match(self) -> None:
        good = dict(self.state["runs"]["77"])
        for key, value in (("event", "push"), ("path", ".github/workflows/other.yml"),
                           ("head_branch", "change/12-add-greeting"), ("triggering_actor", {"login": "owner2"}),
                           ("created_at", "2026-11-16T10:06:00Z"), ("repository", {"full_name": "x/fork"})):
            with self.subTest(key=key):
                self.state["runs"]["77"] = {**good, key: value}
                self.state["issues"]["12"]["comments"] = []
                self.card_record()
                code, out = self.run_check()
                self.assertEqual(code, 1, out)

    def test_record_from_a_branch_workflow_is_ignored(self) -> None:
        self.state["runs"]["77"].update(event="push", head_branch="change/12-add-greeting")
        self.card_record()
        self.assertEqual(self.run_check()[0], 1)

    def test_edited_records_are_ignored(self) -> None:
        self.card_record(updated="2026-11-16T11:00:00Z")
        self.assertEqual(self.run_check()[0], 1)
        terminal = f"<!-- ai-specs:approval digest={self.digest()} commit=abcdef1 by=owner1 -->"
        self.state["issues"]["12"]["comments"] = [{"id": 9, "user": {"login": "owner1"}, "body": terminal,
                                                   "created_at": WHEN, "updated_at": "2026-11-16T11:00:00Z"}]
        self.save()
        self.assertEqual(self.run_check()[0], 1)
        self.state["issues"]["12"]["comments"][0]["updated_at"] = WHEN
        self.save()
        self.assertEqual(self.run_check()[0], 0)

    def test_terminal_and_card_count_together(self) -> None:
        (self.repo / "openspec" / "roles.yaml").write_text("approvers: [owner1, owner2]\nreviewers: [owner1]\n"
                                                           "releasers: [owner1]\nmin_approvals: 2\n", encoding="utf-8")
        self.approve()  # terminal, by owner1
        self.state = self.load()
        self.card_record()  # card, also by owner1: still one approver
        self.assertEqual(self.run_check()[0], 1)
        self.state["runs"]["78"] = {**self.state["runs"]["77"], "triggering_actor": {"login": "owner2"}}
        self.card_record(by="owner2", run="78")
        code, out = self.run_check()
        self.assertEqual(code, 0, out)
        self.assertIn("owner1, owner2", out)

    def test_missing_run_is_exit_1(self) -> None:
        self.card_record(run="404")
        code, out = self.run_check()
        self.assertEqual(code, 1)
        self.assertIn("approve again", out)

    def test_run_lookup_error_is_exit_2(self) -> None:
        self.state["fail_routes"] = ["repos/{owner}/{repo}/actions/runs/77"]
        self.card_record()
        self.assertEqual(self.run_check()[0], 2)

    def test_old_terminal_regex_ignores_card_records(self) -> None:
        self.card_record()
        body = self.state["issues"]["12"]["comments"][-1]["body"]
        self.assertEqual(approval.APPROVAL_RE.findall(body), [])


if __name__ == "__main__":
    unittest.main()
