"""Поведенческие проверки изолированной копии исходников."""

import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


class WorkspaceTests(unittest.TestCase):
    def test_copy_excludes_secrets_and_nested_workspace(self):
        script = Path(__file__).resolve().parents[2] / "scripts" / "security_workspace.py"
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            subprocess.run(["git", "init", "-q", str(root)], check=True)
            (root / ".env").write_text("private", encoding="utf-8")
            source = root / "frontend/src/features/reports"
            source.mkdir(parents=True)
            name = "with space.txt" if os.name == "nt" else "line\nbreak.txt"
            (source / name).write_text("visible", encoding="utf-8")
            work = root / "local-work"
            (work / "source").mkdir(parents=True)
            (work / "secret.txt").write_text("private", encoding="utf-8")
            result = subprocess.run([sys.executable, str(script), str(root), str(work), str(root / "tracked.txt")])
            self.assertEqual(result.returncode, 0)
            self.assertEqual((work / "source/frontend/src/features/reports" / name).read_text(), "visible")
            self.assertFalse((work / "source/.env").exists())
            self.assertFalse((work / "source/local-work").exists())


if __name__ == "__main__":
    unittest.main()
