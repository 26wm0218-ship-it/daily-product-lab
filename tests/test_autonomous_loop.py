"""Guard checks for model proposed local edits."""

from pathlib import Path
import os
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from scripts import autonomous_loop as loop


class ScopeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1])
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.root_patch = patch.object(loop, "ROOT", self.root)
        self.root_patch.start()
        self.addCleanup(self.root_patch.stop)
        (self.root / "docs").mkdir()
        (self.root / "docs" / "verification.md").write_text("before", encoding="utf-8")

    def proposal(self, path="docs/verification.md", expected=None, content="after"):
        if expected is None:
            expected = loop.digest(b"before")
        return {"next_instruction": "Improve verification instructions", "rationale": "clarity",
                "edits": [{"path": path, "expected_sha256": expected, "content": content}]}

    def test_allowed_edit_applies(self):
        changed = loop.validate_and_apply(self.proposal(), ["docs/verification.md"], 100)
        self.assertEqual(changed, ["docs/verification.md"])
        self.assertEqual((self.root / "docs" / "verification.md").read_text(), "after")

    def test_other_path_is_rejected_without_write(self):
        with self.assertRaisesRegex(ValueError, "out-of-scope"):
            loop.validate_and_apply(self.proposal("sources/data.csv"), ["docs/verification.md"], 100)
        self.assertEqual((self.root / "docs" / "verification.md").read_text(), "before")

    def test_stale_or_oversized_edit_is_rejected(self):
        for proposal in (self.proposal(expected="bad"), self.proposal(content="x" * 101)):
            with self.assertRaises(ValueError):
                loop.validate_and_apply(proposal, ["docs/verification.md"], 100)
        self.assertEqual((self.root / "docs" / "verification.md").read_text(), "before")

    def test_worktree_change_outside_allowlist_stops(self):
        status = subprocess.CompletedProcess([], 0, " M docs/verification.md\0 M sources/data.csv\0", "")
        with patch.object(loop, "run_checked", return_value=status):
            with self.assertRaisesRegex(ValueError, "sources/data.csv"):
                loop.check_worktree_scope(["docs/verification.md"])

    def test_staged_or_deleted_change_stops(self):
        for state in ("M ", " D", "??"):
            status = subprocess.CompletedProcess([], 0, f"{state} docs/verification.md\0", "")
            with patch.object(loop, "run_checked", return_value=status):
                with self.assertRaisesRegex(ValueError, "unexpected worktree change"):
                    loop.check_worktree_scope(["docs/verification.md"])

    def test_codex_environment_excludes_credentials(self):
        with patch.dict(os.environ, {"PATH": "test-bin", "OPENAI_API_KEY": "secret",
                                     "AWS_SECRET_ACCESS_KEY": "secret", "GITHUB_TOKEN": "secret"}):
            env = loop.codex_environment()
        self.assertEqual(env["PATH"], "test-bin")
        self.assertNotIn("OPENAI_API_KEY", env)
        self.assertNotIn("AWS_SECRET_ACCESS_KEY", env)
        self.assertNotIn("GITHUB_TOKEN", env)

    def test_protected_snapshot_detects_ignored_and_git_config_changes(self):
        cache = self.root / "ignored.cache"
        cache.write_text("before", encoding="utf-8")
        config = self.root / ".git" / "config"
        config.parent.mkdir()
        config.write_text("before", encoding="utf-8")
        before = loop.protected_snapshot(["docs/verification.md"])
        (self.root / "docs" / "verification.md").write_text("after", encoding="utf-8")
        self.assertEqual(before, loop.protected_snapshot(["docs/verification.md"]))
        cache.write_text("after", encoding="utf-8")
        self.assertNotEqual(before, loop.protected_snapshot(["docs/verification.md"]))
        cache.write_text("before", encoding="utf-8")
        config.write_text("after", encoding="utf-8")
        self.assertNotEqual(before, loop.protected_snapshot(["docs/verification.md"]))


if __name__ == "__main__":
    unittest.main()
