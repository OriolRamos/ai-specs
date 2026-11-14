"""ASP-090 · local leak check: tracked files and ranges, whole words, terms never printed."""
from __future__ import annotations

import io
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

import ai_specs  # noqa: E402
import leakcheck  # noqa: E402

ENV = {"GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@example.invalid",
       "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@example.invalid"}


class LeakCheckTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.repo = Path(self._tmp.name) / "repo"
        self.repo.mkdir()
        self.terms = Path(self._tmp.name) / "terms.txt"
        self.terms.write_text("# internal names\nAcmeCorp\nhidden-repo\n", encoding="utf-8")
        self.env = mock.patch.dict(os.environ, {**ENV, "AI_SPECS_TERMS_FILE": str(self.terms)})
        self.env.start()
        self.git("init", "-q", "-b", "develop")

    def tearDown(self) -> None:
        self.env.stop()
        self._tmp.cleanup()

    def git(self, *args: str) -> str:
        return subprocess.run(["git", "-C", str(self.repo), *args], check=True, capture_output=True, text=True).stdout

    def commit(self, name: str, text: str) -> str:
        (self.repo / name).write_text(text, encoding="utf-8")
        self.git("add", name)
        self.git("commit", "-q", "-m", name)
        return self.git("rev-parse", "HEAD").strip()

    def test_tracked_files_whole_word_case_insensitive(self) -> None:
        self.commit("a.md", "Work for acmecorp.\n")
        self.commit("b.md", "The acmecorporation is unrelated.\n")
        self.commit("c.md", "See HIDDEN-REPO docs.\n")
        self.assertEqual(leakcheck.scan(self.repo, leakcheck.load_terms()), ["a.md", "c.md"])

    def test_range_checks_only_added_lines(self) -> None:
        first = self.commit("a.md", "AcmeCorp was here.\n")
        last = self.commit("b.md", "Clean text.\n")
        self.assertEqual(leakcheck.scan(self.repo, leakcheck.load_terms(), f"{first}..{last}"), [])
        leaky = self.commit("c.md", "Mentions AcmeCorp again.\n")
        self.assertEqual(leakcheck.scan(self.repo, leakcheck.load_terms(), f"{last}..{leaky}"), ["c.md"])

    def test_cli_never_prints_the_terms(self) -> None:
        self.commit("a.md", "AcmeCorp\n")
        out = io.StringIO()
        with redirect_stdout(out):
            code = ai_specs.main(["leak-check", str(self.repo)])
        self.assertEqual(code, 1)
        self.assertIn("a.md", out.getvalue())
        self.assertNotIn("acmecorp", out.getvalue().lower())

    def test_no_terms_file_checks_nothing(self) -> None:
        self.terms.unlink()
        self.commit("a.md", "AcmeCorp\n")
        with redirect_stdout(io.StringIO()):
            self.assertEqual(ai_specs.main(["leak-check", str(self.repo)]), 0)


if __name__ == "__main__":
    unittest.main()
