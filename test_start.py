"""Unit tests for NeuroOptic One-Click Starter (start.py)."""

import io
import os
import sys
import unittest
from unittest import mock

# Ensure project directory is in sys.path
sys.path.insert(0, os.path.dirname(__file__))

import start


class StartScriptTests(unittest.TestCase):
    def test_check_dependencies_returns_true_in_configured_environment(self):
        ok, missing = start.check_dependencies()
        self.assertTrue(ok)
        self.assertEqual(missing, [])

    def test_check_dependencies_detects_missing_module(self):
        with mock.patch("importlib.util.find_spec", return_value=None):
            ok, missing = start.check_dependencies()
            self.assertFalse(ok)
            self.assertGreaterEqual(len(missing), 1)

    def test_build_quick_command_gamma(self):
        cmd = start.build_quick_command(preset="gamma", dry_run=False)
        self.assertIn("--freq", cmd)
        self.assertIn("40.0", cmd)
        self.assertIn("--waveform", cmd)
        self.assertIn("sine", cmd)
        self.assertIn("--ramp", cmd)
        self.assertIn("5.0", cmd)
        self.assertNotIn("--dry-run", cmd)

    def test_build_quick_command_alpha_dry_run(self):
        cmd = start.build_quick_command(preset="alpha", dry_run=True)
        self.assertIn("--freq", cmd)
        self.assertIn("10.0", cmd)
        self.assertIn("--dry-run", cmd)

    def test_print_remediation_error_format(self):
        captured_err = io.StringIO()
        with mock.patch("sys.stderr", captured_err):
            start.print_remediation_error(
                what="Test operation failed.",
                why="Unit test simulated error.",
                fix="Run test diagnostic command."
            )
        output = captured_err.getvalue()
        self.assertIn("Error: Test operation failed.", output)
        self.assertIn("Why: Unit test simulated error.", output)
        self.assertIn("Fix: Run test diagnostic command.", output)

    def test_main_check_flag(self):
        with mock.patch.object(sys, "argv", ["start.py", "--check"]):
            ret = start.main()
            self.assertEqual(ret, 0)

    def test_main_dry_run_gamma(self):
        with mock.patch.object(sys, "argv", ["start.py", "--dry-run"]):
            ret = start.main()
            self.assertEqual(ret, 0)

    def test_main_missing_dependencies_exits_one(self):
        with mock.patch("start.check_dependencies", return_value=(False, ["nonexistent_pkg"])):
            with mock.patch.object(sys, "argv", ["start.py"]):
                ret = start.main()
                self.assertEqual(ret, 1)

    def test_main_quick_popen_invoked(self):
        with mock.patch("subprocess.Popen") as mock_popen:
            with mock.patch.object(sys, "argv", ["start.py", "--quick"]):
                ret = start.main()
                self.assertEqual(ret, 0)
                mock_popen.assert_called_once()
                cmd = mock_popen.call_args[0][0]
                self.assertIn("40.0", cmd)


if __name__ == "__main__":
    unittest.main()
