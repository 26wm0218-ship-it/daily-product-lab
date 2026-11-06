"""Exercise the repository verifier against safe copies of its inputs."""

from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


SOURCE = Path(__file__).resolve().parents[1]
INPUTS = (
    "AGENTS.md",
    "README.md",
    "ideas/backlog.yml",
    "prompts/generate-draft.md",
    "scripts/verify.py",
)


class VerifyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=SOURCE)
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        for name in INPUTS:
            target = self.root / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(SOURCE / name, target)

    def run_verifier(self):
        return subprocess.run(
            [sys.executable, str(self.root / "scripts/verify.py")],
            cwd=self.root,
            capture_output=True,
            text=True,
            check=False,
        )

    def test_current_backlog_passes(self):
        result = self.run_verifier()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("7 backlog items", result.stdout)

    def test_missing_backlog_field_fails(self):
        backlog = self.root / "ideas/backlog.yml"
        text = backlog.read_text(encoding="utf-8")
        self.assertIn("    product_metric:", text)
        backlog.write_text(text.replace("    product_metric:", "    removed_product_metric:", 1), encoding="utf-8")
        result = self.run_verifier()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("backlog field 'product_metric'", result.stdout)

    def test_incomplete_draft_fails(self):
        draft = self.root / "content/drafts/example.md"
        draft.parent.mkdir(parents=True)
        draft.write_text("# Example\n対象者: reader\n", encoding="utf-8")
        result = self.run_verifier()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("missing section '課題'", result.stdout)


if __name__ == "__main__":
    unittest.main()
