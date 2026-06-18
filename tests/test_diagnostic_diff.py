#!/usr/bin/env python3
"""
Tests for diagnostic_diff tool (issue #5).
"""

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
from diagnostic_diff import diff_diagnostics, render_text, load_diagnostic


BASELINE_DATA = {
    "commit": "abc12345",
    "total_modules": 3,
    "passed": 2,
    "failed": 1,
    "chunked": False,
    "modules": [
        {"name": "backend", "status": "PASS", "elapsed_seconds": 5.2, "artifact": "bin/backend", "output": "ok"},
        {"name": "frontend", "status": "PASS", "elapsed_seconds": 3.1, "artifact": "dist/", "output": "ok"},
        {"name": "frailbox", "status": "FAIL", "elapsed_seconds": 0, "artifact": None, "output": "make not found"},
    ],
}

CURRENT_DATA = {
    "commit": "def67890",
    "total_modules": 3,
    "passed": 3,
    "failed": 0,
    "chunked": False,
    "modules": [
        {"name": "backend", "status": "PASS", "elapsed_seconds": 4.8, "artifact": "bin/backend", "output": "ok"},
        {"name": "frontend", "status": "PASS", "elapsed_seconds": 3.1, "artifact": "dist/", "output": "ok"},
        {"name": "frailbox", "status": "PASS", "elapsed_seconds": 1.2, "artifact": "bin/frailbox", "output": "ok"},
    ],
}


class TestDiagnosticDiff(unittest.TestCase):

    def _write_temp(self, data):
        fd, path = tempfile.mkstemp(suffix=".json")
        with os.fdopen(fd, "w") as f:
            json.dump(data, f)
        return path

    def test_diff_detects_changed_fields(self):
        result = diff_diagnostics(BASELINE_DATA, CURRENT_DATA)
        self.assertGreater(result["summary"]["total_changes"], 0)
        self.assertTrue(result["summary"]["passed_changed"])
        self.assertTrue(result["summary"]["failed_changed"])

    def test_diff_detects_module_status_change(self):
        result = diff_diagnostics(BASELINE_DATA, CURRENT_DATA)
        frailbox_changes = [c for c in result["changes"] if "frailbox" in c["field"]]
        self.assertGreater(len(frailbox_changes), 0)
        status_change = [c for c in frailbox_changes if c["field"] == "module.frailbox.status"]
        self.assertEqual(len(status_change), 1)
        self.assertEqual(status_change[0]["baseline"], "FAIL")
        self.assertEqual(status_change[0]["current"], "PASS")

    def test_diff_identical_diagnostics_no_changes(self):
        result = diff_diagnostics(BASELINE_DATA, BASELINE_DATA)
        self.assertEqual(result["summary"]["total_changes"], 0)

    def test_diff_detects_added_module(self):
        current = json.loads(json.dumps(CURRENT_DATA))
        current["modules"].append({"name": "newmod", "status": "PASS", "elapsed_seconds": 1, "artifact": None, "output": "ok"})
        result = diff_diagnostics(BASELINE_DATA, current)
        self.assertEqual(result["summary"]["modules_added"], 1)

    def test_diff_detects_removed_module(self):
        baseline = json.loads(json.dumps(BASELINE_DATA))
        baseline["modules"].append({"name": "extramod", "status": "PASS", "elapsed_seconds": 1, "artifact": None, "output": "ok"})
        result = diff_diagnostics(baseline, CURRENT_DATA)
        self.assertEqual(result["summary"]["modules_removed"], 1)

    def test_render_text_produces_markdown(self):
        result = diff_diagnostics(BASELINE_DATA, CURRENT_DATA)
        text = render_text(result)
        self.assertIn("# Diagnostic Diff Report", text)
        self.assertIn("abc12345", text)
        self.assertIn("def67890", text)

    def test_render_text_identical(self):
        result = diff_diagnostics(BASELINE_DATA, BASELINE_DATA)
        text = render_text(result)
        self.assertIn("No differences detected", text)

    def test_load_diagnostic_file_not_found(self):
        with self.assertRaises(FileNotFoundError):
            load_diagnostic("/nonexistent/path.json")


if __name__ == "__main__":
    unittest.main()
