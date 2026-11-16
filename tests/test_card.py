"""ASP-111 … ASP-115: the approval card, rendered from a real git branch and driven through a fake `gh`."""
from __future__ import annotations

import io
import json
import os
import subprocess
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
import card  # noqa: E402

URL = "https://github.com/o/r"
BRANCH = "change/12-demo"
BLOCK = f"<!-- ai-specs:change -->\nchange: demo\nbranch: {BRANCH}\nsize: S\n<!-- /ai-specs:change -->\n"
BOT = {"login": "github-actions[bot]", "type": "Bot"}
PROPOSAL = """**Size:** S

## Why
Callers need a greeting.

## What Changes
- Add `GET /greet` in `scripts/greet.py`.
- **Excludes:** localisation.

## Not to add
- No auth.
"""
SPEC = """## Purpose

Greets every caller by name so all clients show the same predictable text.

## ADDED Requirements

### Requirement: EE-001 — Greeting by name
The service SHALL return a greeting that contains the caller's name.

#### Scenario: Named greeting
- **GIVEN** a caller named Ada
- **WHEN** it calls `GET /greet?name=Ada`
- **THEN** the response is `200`
- **Proof:** `pytest -q` passes
"""
TASKS = """## 1. Greeting
- [ ] 1.1 Greeting endpoint — test first: `t` — proof: `p`
- [ ] 1.2 Owner reviews `.github/workflows/ai-specs.yml` changes before merge — test first: n/a — proof: `p` (human gate)
"""


def git(cwd: Path, *args: str) -> str:
    env = {**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@example.invalid",
           "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@example.invalid"}
    return subprocess.run(["git", "-C", str(cwd), *args], capture_output=True, text=True, check=True,
                          env=env).stdout.strip()


class CardFixture(unittest.TestCase):
    """A default-branch checkout (`base`, roles), a change branch checkout (`src`) and a fake gh."""

    roles = "approvers: [owner]\nreviewers: [owner]\nreleasers: [owner]\nmin_approvals: 1\n"

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        tmp = Path(self._tmp.name)
        self.base, self.src = tmp / "base", tmp / "src"
        (self.base / "openspec").mkdir(parents=True)
        (self.base / "openspec" / "roles.yaml").write_text(self.roles, encoding="utf-8")
        self.folder = self.src / "openspec" / "changes" / "demo"
        (self.folder / "specs" / "greeting").mkdir(parents=True)
        (self.folder / "proposal.md").write_text(PROPOSAL, encoding="utf-8")
        (self.folder / "specs" / "greeting" / "spec.md").write_text(SPEC, encoding="utf-8")
        (self.folder / "tasks.md").write_text(TASKS, encoding="utf-8")
        git(self.src.parent, "init", "-q", "-b", BRANCH, str(self.src))
        self.commit("first")
        bindir = tmp / "bin"
        bindir.mkdir()
        gh = bindir / "gh"
        gh.write_text(f"#!/bin/sh\nexec {sys.executable} {KIT / 'tests' / 'fake_gh.py'} \"$@\"\n", encoding="utf-8")
        gh.chmod(0o755)
        self.state_file = tmp / "gh.json"
        self.state = {"login": "github-actions[bot]", "branches": {BRANCH: self.head()},
                      "issues": {"12": {"body": BLOCK, "labels": ["type:change", "state:proposed"], "comments": []}},
                      "runs": {}}
        self.save()
        self.env = mock.patch.dict(os.environ, {"PATH": f"{bindir}{os.pathsep}{os.environ['PATH']}",
                                                "FAKE_GH_STATE": str(self.state_file)})
        self.env.start()

    def tearDown(self) -> None:
        self.env.stop()
        self._tmp.cleanup()

    # -- helpers
    def commit(self, message: str) -> str:
        git(self.src, "add", "-A")
        git(self.src, "commit", "-q", "-m", message)
        return self.head()

    def head(self) -> str:
        return git(self.src, "rev-parse", "HEAD")

    def save(self) -> None:
        self.state_file.write_text(json.dumps(self.state), encoding="utf-8")

    def load(self) -> dict:
        self.state = json.loads(self.state_file.read_text(encoding="utf-8"))
        return self.state

    def digest(self) -> str:
        return approval.digest(self.folder)

    def meta(self, commit: str | None = None) -> card.Meta:
        return card.Meta("demo", 12, BRANCH, commit or self.head(), URL, "openspec/changes/demo")

    def issue_event(self, **issue: object) -> dict:
        data = {"number": 12, "state": "open", "body": BLOCK,
                "labels": [{"name": n} for n in self.state["issues"]["12"]["labels"]], **issue}
        return {"action": "edited", "issue": data, "repository": {"html_url": URL},
                "sender": {"login": "owner", "type": "User"}}

    def push_event(self, ref: str = f"refs/heads/{BRANCH}") -> dict:
        return {"ref": ref, "repository": {"html_url": URL}, "sender": {"login": "owner", "type": "User"}}

    def sync(self, event: dict | None = None) -> str:
        self.state = self.load()
        self.state["branches"][BRANCH] = self.head()
        self.save()
        return card.sync(self.base, self.src, event or self.push_event())

    def cards(self) -> list[dict]:
        return [c for c in self.load()["issues"]["12"]["comments"] if c["body"].startswith(card.CARD_PREFIX)]

    def records(self) -> list[dict]:
        return [c for c in self.load()["issues"]["12"]["comments"] if "ai-specs:approval digest=" in c["body"]]

    def labels(self) -> list[str]:
        return sorted(self.load()["issues"]["12"]["labels"])


class RenderTest(CardFixture):
    def test_card_shows_scope_links_and_one_box(self) -> None:
        body = card.render(self.folder, self.meta())
        sha, value = self.head(), self.digest()
        self.assertTrue(body.startswith(f"<!-- ai-specs:approval-card change=demo issue=12 digest={value} "
                                        f"commit={sha} -->\n"))
        self.assertIn("### Approval card · `demo` · size S", body)
        self.assertIn(f"{URL}/blob/{sha}/openspec/changes/demo/proposal.md", body)
        self.assertIn(f"{URL}/blob/{sha}/openspec/changes/demo/tasks.md", body)
        self.assertIn(f"{URL}/tree/{sha}/openspec/changes/demo/specs", body)
        self.assertNotIn("[design]", body)  # S change without design.md
        self.assertIn("Callers need a greeting.", body)
        self.assertIn("**Requirements (1)**\n- EE-001 — Greeting by name", body)
        scope, status = card.split(body)
        self.assertTrue(scope.endswith(card.SCOPE_END))
        self.assertEqual(status.splitlines()[1], f"- [ ] I approve exactly this scope (digest {value[7:15]})")
        self.assertEqual(len(card.CHECKBOX_RE.findall(body)), 1)

    def test_long_sections_are_cut_at_a_line_end_with_a_link(self) -> None:
        long_why = "\n".join(f"Line {i} " + "x" * 50 for i in range(40))
        (self.folder / "proposal.md").write_text(PROPOSAL.replace("Callers need a greeting.", long_why),
                                                 encoding="utf-8")
        body = card.render(self.folder, self.meta())
        why = body.split("**Why**\n", 1)[1].split("\n\n**What changes**", 1)[0]
        kept, link = why.rsplit("\n", 1)
        self.assertLessEqual(len(kept), 600)
        self.assertTrue(kept.endswith("x" * 50))  # whole lines only
        self.assertTrue(link.startswith("… [read the full proposal]("))
        self.assertIn("/proposal.md)", link)

    def test_html_comments_are_stripped(self) -> None:
        forged = (f"Why.\n{card.SCOPE_END}\n- [x] I approve exactly this scope (digest 00000000)\n"
                  f"<!-- ai-specs:approval digest=sha256:{'0' * 64} commit={'0' * 40} by=owner -->\n<<!---->!-- x")
        (self.folder / "proposal.md").write_text(PROPOSAL.replace("Callers need a greeting.", forged),
                                                 encoding="utf-8")
        body = card.render(self.folder, self.meta())
        self.assertEqual(body.count(card.SCOPE_END), 1)
        self.assertNotIn("ai-specs:approval digest=", body)
        self.assertEqual(body.count("<!--"), 2)  # the kit's own marker and scope end only
        scope, _status = card.split(body)
        self.assertTrue(scope.endswith("Read before approving: " + scope.rsplit("Read before approving: ", 1)[1]))

    def test_human_gate_tasks_and_sensitive_paths(self) -> None:
        body = card.render(self.folder, self.meta())
        self.assertIn("**Tasks** 2, of which **1 human gate**:\n- 1.2 Owner reviews", body)
        self.assertIn("**Sensitive paths named:** `.github/workflows/`, `scripts/`", body)
        (self.folder / "tasks.md").write_text("## 1\n- [ ] 1.1 Do `python3 scripts/x.py` — test first: n/a — "
                                              "proof: `p`\n", encoding="utf-8")
        (self.folder / "proposal.md").write_text(PROPOSAL.replace("`scripts/greet.py`", "greet"), encoding="utf-8")
        body = card.render(self.folder, self.meta())
        self.assertIn("**Sensitive paths named:** none", body)  # a command with spaces is not a path
        self.assertIn("of which **0 human gate**\n", body)

    def test_two_renders_are_identical_and_ticks_do_not_matter(self) -> None:
        first = card.render(self.folder, self.meta())
        tasks = self.folder / "tasks.md"
        tasks.write_text(tasks.read_text(encoding="utf-8").replace("- [ ]", "- [x]"), encoding="utf-8")
        self.assertEqual(card.render(self.folder, self.meta()), first)

    def test_size_cap_cuts_requirements_first(self) -> None:
        many = "".join(f"\n### Requirement: EE-{i:03d} — {'Long title ' * 20}\nThe service SHALL work.\n\n"
                       f"#### Scenario: S\n- **GIVEN** a\n- **WHEN** b\n- **THEN** c\n- **Proof:** `p`\n"
                       for i in range(400))
        (self.folder / "specs" / "greeting" / "spec.md").write_text(SPEC + many, encoding="utf-8")
        body = card.render(self.folder, self.meta())
        self.assertLessEqual(len(body), card.CARD_CAP)
        self.assertIn("**Requirements (401)**", body)
        self.assertRegex(body, r"- and \d+ more")
        self.assertIn("- 1.2 Owner reviews", body)  # human-gate tasks kept
        self.assertTrue(card.split(body)[1].lstrip().startswith("- [ ] I approve"))


class SyncTest(CardFixture):
    def test_first_render_posts_one_card(self) -> None:
        self.sync()
        self.sync(self.issue_event())  # an issue edit with the same head writes nothing new
        cards = self.cards()
        self.assertEqual(len(cards), 1)
        self.assertEqual(cards[0]["user"]["login"], "github-actions[bot]")
        self.assertEqual(cards[0]["body"], card.render(self.folder, self.meta()))
        self.assertEqual(cards[0]["created_at"], cards[0]["updated_at"])

    def test_new_digest_resets_card_and_state(self) -> None:
        self.sync()
        self.state = self.load()
        self.state["issues"]["12"]["labels"] = ["type:change", "state:approved"]
        self.save()
        (self.folder / "proposal.md").write_text(PROPOSAL.replace("greeting.", "greeting now."), encoding="utf-8")
        self.commit("reword")
        self.sync()
        cards = self.cards()
        self.assertEqual(len(cards), 1)
        self.assertIn(f"digest={self.digest()} commit={self.head()}", cards[0]["body"])
        self.assertIn("- [ ] I approve", cards[0]["body"])
        self.assertEqual(self.labels(), ["state:proposed", "type:change"])

    def test_ticked_tasks_keep_card_and_state(self) -> None:
        self.sync()
        before = self.cards()[0]
        self.state = self.load()
        self.state["issues"]["12"]["labels"] = ["type:change", "state:in-progress"]
        self.save()
        tasks = self.folder / "tasks.md"
        tasks.write_text(tasks.read_text(encoding="utf-8").replace("- [ ] 1.1", "- [x] 1.1"), encoding="utf-8")
        self.commit("tick")
        self.sync()
        self.assertEqual(self.cards(), [before])
        self.assertEqual(self.labels(), ["state:in-progress", "type:change"])

    def test_missing_branch_writes_nothing(self) -> None:
        self.state["issues"]["13"] = {"body": BLOCK.replace("12-demo", "13-demo"), "comments": [],
                                      "labels": ["type:change", "state:proposed"]}
        self.save()
        event = self.issue_event(number=13, body=BLOCK.replace("12-demo", "13-demo"))
        event["action"] = "opened"
        self.assertIn("does not exist yet", card.sync(self.base, self.src, event))
        state = self.load()
        self.assertEqual(state["issues"]["13"]["comments"], [])
        self.assertEqual(state["issues"]["13"]["labels"], ["type:change", "state:proposed"])

    def test_stray_branch_writes_nothing(self) -> None:
        self.state["branches"]["change/12-other"] = self.head()
        self.save()
        out = card.sync(self.base, self.src, self.push_event("refs/heads/change/12-other"))
        self.assertIn("is not the branch #12 names", out)
        self.assertEqual(self.cards(), [])

    def test_closed_issue_and_bad_blocks_write_nothing(self) -> None:
        cases = {"closed": self.issue_event(state="closed"),
                 "no block": self.issue_event(body="plain text"),
                 "other issue's branch": self.issue_event(body=BLOCK.replace("12-demo", "13-demo")),
                 "bad change id": self.issue_event(body=BLOCK.replace("change: demo", "change: Demo_X")),
                 "not a change": self.issue_event(labels=[{"name": "bug"}]),
                 "pull request": self.issue_event(pull_request={"url": "x"}),
                 "not a change branch": self.push_event("refs/heads/feature/x")}
        for name, event in cases.items():
            with self.subTest(name):
                self.assertTrue(card.sync(self.base, self.src, event).startswith("notice:"))
        self.assertEqual(self.cards(), [])

    def test_missing_folder_writes_nothing(self) -> None:
        git(self.src, "rm", "-q", "-r", "openspec")
        self.commit("drop")
        self.assertIn("is not on change/12-demo yet", self.sync())
        self.assertEqual(self.cards(), [])

    def test_archived_folder_is_rendered(self) -> None:
        archive = self.src / "openspec" / "changes" / "archive"
        archive.mkdir()
        self.folder.rename(archive / "2026-11-16-demo")
        self.commit("archive")
        self.sync()
        self.assertIn("/openspec/changes/archive/2026-11-16-demo/proposal.md", self.cards()[0]["body"])


class ReviewTest(CardFixture):
    def run_record(self, run_id: str, who: str) -> None:
        self.state = self.load()
        self.state["runs"][run_id] = {"event": "issue_comment", "path": approval.CARD_WORKFLOW,
                                      "head_branch": "develop", "triggering_actor": {"login": who},
                                      "created_at": "2026-11-16T09:00:00Z"}
        self.save()

    def tick(self, who: str = "owner", run_id: str = "77", edit=None, comment: dict | None = None) -> tuple[int, str]:
        """`who` ticks the card in the UI: GitHub saves the edit, then the workflow reviews it."""
        self.run_record(run_id, who)
        target = comment or self.cards()[0]
        body = target["body"].replace("- [ ] I approve", "- [x] I approve", 1)
        body = edit(body) if edit else body
        for note in self.state["issues"]["12"]["comments"]:
            if note["id"] == target["id"]:
                note["body"] = body
                note["updated_at"] = "2026-11-16T12:00:00Z"
        self.save()
        event = self.issue_event()
        event["comment"] = {"id": target["id"], "body": body, "user": BOT}
        event["sender"] = {"login": who, "type": "User"}
        return card.review(self.base, self.src, event, run_id)

    def check(self) -> tuple[int, str]:
        (self.src / "openspec" / "roles.yaml").write_text(self.roles, encoding="utf-8")
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = ai_specs.main(["check-approval", str(self.src), "12"])
        return code, out.getvalue() + err.getvalue()

    def test_approver_tick_records_and_approves(self) -> None:
        self.sync()
        code, _msg = self.tick()
        self.assertEqual(code, 0)
        records = self.records()
        self.assertEqual(len(records), 1)
        self.assertIn(f"digest={self.digest()} commit={self.head()} by=owner via=card run=77 -->", records[0]["body"])
        self.assertIn("@owner", records[0]["body"])
        self.assertEqual(self.labels(), ["state:approved", "type:change"])
        body = self.cards()[0]["body"]
        self.assertIn("- [ ] I approve", body)
        self.assertIn("Approvals for this digest: @owner (1 of 1)", body)
        self.assertEqual(self.check()[0], 0)

    def test_min_approvals_two(self) -> None:
        self.roles = "approvers: [a, b]\nreviewers: [a]\nreleasers: [a]\nmin_approvals: 2\n"
        (self.base / "openspec" / "roles.yaml").write_text(self.roles, encoding="utf-8")
        self.sync()
        self.assertEqual(self.tick("a", "77")[0], 0)
        self.assertEqual(self.labels(), ["state:proposed", "type:change"])
        self.assertIn("@a (1 of 2)", self.cards()[0]["body"])
        self.assertEqual(self.tick("b", "78")[0], 0)
        self.assertEqual(self.labels(), ["state:approved", "type:change"])
        self.assertEqual(len(self.records()), 2)
        self.assertIn("@a, @b (2 of 2)", self.cards()[0]["body"])
        self.assertEqual(self.check()[0], 0)

    def test_non_approver_is_undone(self) -> None:
        self.sync()
        code, _msg = self.tick("someone")
        self.assertEqual(code, 1)
        self.assertEqual(self.records(), [])
        body = self.cards()[0]["body"]
        self.assertIn("- [ ] I approve", body)
        self.assertIn("@someone is not an approver of this repo", body)
        self.assertEqual(self.labels(), ["state:proposed", "type:change"])

    def test_branch_roles_do_not_make_an_approver(self) -> None:
        (self.src / "openspec" / "roles.yaml").write_text("approvers: [owner, someone]\n", encoding="utf-8")
        self.commit("add myself")  # roles come from the default branch, not from the change branch
        self.sync()
        self.assertEqual(self.tick("someone")[0], 1)
        self.assertEqual(self.records(), [])

    def test_stale_card_is_undone(self) -> None:
        self.sync()
        old = self.digest()
        (self.folder / "proposal.md").write_text(PROPOSAL.replace("greeting.", "greeting now."), encoding="utf-8")
        self.commit("reword")  # the push run has not redrawn the card yet
        self.state = self.load()
        self.state["branches"][BRANCH] = self.head()
        self.save()
        code, _msg = self.tick()
        self.assertEqual(code, 1)
        self.assertEqual(self.records(), [])
        body = self.cards()[0]["body"]
        self.assertNotIn(old, body)
        self.assertIn(f"digest={self.digest()}", body)
        self.assertIn("the scope changed since this card was drawn", body)
        self.assertIn("- [ ] I approve", body)

    def test_altered_card_is_restored(self) -> None:
        self.sync()
        original = card.split(self.cards()[0]["body"])[0]
        code, _msg = self.tick(edit=lambda b: b.replace("Callers need a greeting.", "Nothing changes, trust me."))
        self.assertEqual(code, 1)
        self.assertEqual(self.records(), [])
        body = self.cards()[0]["body"]
        self.assertEqual(card.split(body)[0], original)
        self.assertIn("the card text was changed", body)
        self.assertIn("- [ ] I approve", body)

    def test_forged_marker_commit_is_restored(self) -> None:
        self.sync()
        first = self.head()
        (self.folder / "proposal.md").write_text(PROPOSAL.replace("greeting.", "greeting now."), encoding="utf-8")
        self.commit("reword")
        self.sync()
        # someone points the card at the older commit, whose files say something else, keeping the new digest
        code, _msg = self.tick(edit=lambda b: b.replace(self.head(), first))
        self.assertEqual(code, 1)
        self.assertIn("the card text was changed", self.cards()[0]["body"])
        self.assertIn(f"commit={self.head()}", self.cards()[0]["body"])

    def test_card_drawn_before_a_ticks_only_push_still_approves(self) -> None:
        self.sync()
        drawn = self.head()
        tasks = self.folder / "tasks.md"
        tasks.write_text(tasks.read_text(encoding="utf-8").replace("- [ ] 1.1", "- [x] 1.1"), encoding="utf-8")
        self.commit("tick")
        self.sync()
        self.assertIn(f"commit={drawn}", self.cards()[0]["body"])
        self.assertEqual(self.tick()[0], 0)
        self.assertIn(f"commit={self.head()} by=owner", self.records()[0]["body"])

    def test_windows_line_endings_from_the_web_editor(self) -> None:
        self.sync()
        self.assertEqual(self.tick(edit=lambda b: b.replace("\n", "\r\n"))[0], 0)
        self.assertEqual(len(self.records()), 1)

    def test_not_the_sticky_card(self) -> None:
        self.sync()
        self.state = self.load()
        dup = dict(self.cards()[0], id=5000)
        self.state["issues"]["12"]["comments"].append(dup)
        self.save()
        code, _msg = self.tick(comment=dup)
        self.assertEqual(code, 1)
        self.assertEqual(self.records(), [])
        second = [c for c in self.cards() if c["id"] == 5000][0]
        self.assertIn("use the first card", second["body"])
        self.assertIn("- [ ] I approve", second["body"])

    def test_closed_issue(self) -> None:
        self.sync()
        self.run_record("77", "owner")
        target = self.cards()[0]
        body = target["body"].replace("- [ ]", "- [x]", 1)
        event = self.issue_event(state="closed")
        event["comment"] = {"id": target["id"], "body": body, "user": BOT}
        code, _msg = card.review(self.base, self.src, event, "77")
        self.assertEqual(code, 1)
        self.assertEqual(self.records(), [])
        self.assertIn("the issue is not an open change", self.cards()[0]["body"])
        self.assertIn("- [ ] I approve", self.cards()[0]["body"])

    def test_untick_edit_redraws_without_record(self) -> None:
        self.sync()
        target = self.cards()[0]
        event = self.issue_event()
        event["comment"] = {"id": target["id"], "body": target["body"] + "\nextra", "user": BOT}
        self.assertEqual(card.review(self.base, self.src, event, "77")[0], 0)
        self.assertEqual(self.records(), [])
        self.assertEqual(self.cards()[0]["body"], card.render(self.folder, self.meta()))

    def test_bot_edits_and_other_comments_are_ignored(self) -> None:
        self.sync()
        target = self.cards()[0]
        event = self.issue_event()
        event["comment"] = {"id": target["id"], "body": target["body"].replace("- [ ]", "- [x]"), "user": BOT}
        event["sender"] = {"login": "github-actions[bot]", "type": "Bot"}
        self.assertEqual(card.review(self.base, self.src, event, "77")[0], 0)
        event["sender"] = {"login": "owner", "type": "User"}
        event["comment"]["user"] = {"login": "owner", "type": "User"}
        self.assertEqual(card.review(self.base, self.src, event, "77")[0], 0)
        self.assertEqual(self.records(), [])
        with self.assertRaises(card.CardError):
            card.review(self.base, self.src, event, "")

    def test_rerun_is_idempotent(self) -> None:
        self.sync()
        self.assertEqual(self.tick()[0], 0)
        self.assertEqual(self.tick()[0], 0)  # the same run re-run, or a second tick by the same approver
        self.assertEqual(len(self.records()), 1)
        self.assertEqual(self.labels(), ["state:approved", "type:change"])

    def test_label_recount_after_race(self) -> None:
        self.roles = "approvers: [a, b]\nreviewers: [a]\nreleasers: [a]\nmin_approvals: 2\n"
        (self.base / "openspec" / "roles.yaml").write_text(self.roles, encoding="utf-8")
        self.sync()
        value = self.digest()
        real = card.ghcli.comments
        calls = {"n": 0}

        def comments(cwd: Path, number: int) -> list[dict]:
            calls["n"] += 1
            if calls["n"] == 3:  # b's record lands between a's first count and its recount
                self.load()
                self.state["issues"]["12"]["comments"].append(
                    {"id": 4000, "user": BOT, "created_at": "2026-11-16T11:00:00Z",
                     "updated_at": "2026-11-16T11:00:00Z",
                     "body": f"<!-- ai-specs:approval digest={value} commit={self.head()} by=b via=card run=78 -->"})
                self.save()
            return real(cwd, number)

        writes: list[str] = []
        real_set = card.ghcli.set_state

        def set_state(cwd: Path, number: int, state: str) -> None:
            writes.append(state)
            real_set(cwd, number, state)

        with mock.patch.object(card.ghcli, "comments", comments), mock.patch.object(card.ghcli, "set_state", set_state):
            self.assertEqual(self.tick("a", "77")[0], 0)
        self.assertNotIn("state:proposed", writes)
        self.assertEqual(self.labels(), ["state:approved", "type:change"])
        self.assertIn("@a, @b (2 of 2)", self.cards()[0]["body"])


if __name__ == "__main__":
    unittest.main()
