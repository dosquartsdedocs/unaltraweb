from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.validate_workflows import load_workflow, validate_workflows


class WorkflowTests(unittest.TestCase):
    def test_repository_workflows_satisfy_static_policy(self) -> None:
        self.assertEqual(validate_workflows(), [])

    def test_loader_preserves_on_and_rejects_duplicate_keys(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            path = Path(raw) / "workflow.yml"
            path.write_text("on:\n  push:\njobs: {}\n", encoding="utf-8")
            self.assertIn("on", load_workflow(path))
            path.write_text("name: first\nname: second\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "duplicate YAML key"):
                load_workflow(path)


if __name__ == "__main__":
    unittest.main()
