"""Check onboarding without contacting Things or changing system settings."""

import os
from pathlib import Path
import subprocess
import tempfile
import unittest


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "check_setup.sh"


class SetupTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="things setup ")
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)
        self.calls = self.directory / "calls"
        self.python = self.directory / "python with spaces"
        self.uname = self.directory / "uname"
        self.uname.write_text('#!/bin/sh\nprintf "%s\\n" Darwin\n')
        self.uname.chmod(0o755)
        self.python.write_text(
            '#!/bin/sh\n'
            'printf "%s\\n" "$*" >> "$THINGS_TEST_CALLS"\n'
            'if [ "$1" = -c ]; then\n'
            '  printf "%s\\n" 3.12.0\n'
            '  exit "${THINGS_TEST_VERSION_EXIT:-0}"\n'
            'fi\n'
            'printf "%s\\n" \'{"ok": true, "connected": true, "version": "test"}\'\n'
            'exit "${THINGS_TEST_STATUS_EXIT:-0}"\n'
        )
        self.python.chmod(0o755)
        self.env = dict(os.environ, PATH=str(self.directory) + os.pathsep + os.defpath,
                        THINGS_PYTHON=str(self.python), THINGS_TEST_CALLS=str(self.calls))

    def invoke(self, *args):
        return subprocess.run(["/bin/sh", str(SCRIPT), *args], env=self.env, text=True, capture_output=True, check=False)

    def test_prerequisites_do_not_contact_things(self):
        result = self.invoke("--no-connect")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("has not been checked", result.stdout)
        self.assertNotIn("things.py", self.calls.read_text())

    def test_default_setup_only_calls_status_and_handles_paths_with_spaces(self):
        result = self.invoke()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('"connected": true', result.stdout)
        calls = self.calls.read_text().splitlines()
        self.assertEqual(len(calls), 2)
        self.assertEqual(calls[1], str(SCRIPT.with_name("things.py")) + " status")

    def test_connection_failure_keeps_nonzero_exit_status(self):
        self.env["THINGS_TEST_STATUS_EXIT"] = "1"
        self.assertEqual(self.invoke().returncode, 1)

    def test_old_python_does_not_try_to_connect(self):
        self.env["THINGS_TEST_VERSION_EXIT"] = "1"
        result = self.invoke()
        self.assertEqual(result.returncode, 1)
        self.assertIn("Python 3.10 or later", result.stderr)
        self.assertNotIn("things.py", self.calls.read_text())

    def test_missing_selected_python_is_explained(self):
        self.env["THINGS_PYTHON"] = str(self.directory / "missing")
        result = self.invoke()
        self.assertEqual(result.returncode, 1)
        self.assertIn("THINGS_PYTHON", result.stderr)
        self.assertFalse(self.calls.exists())

    def test_non_mac_stops_before_python_or_automation(self):
        self.uname.write_text('#!/bin/sh\nprintf "%s\\n" Linux\n')
        result = self.invoke()
        self.assertEqual(result.returncode, 1)
        self.assertIn("execution on a Mac", result.stderr)
        self.assertFalse(self.calls.exists())

    def test_help_and_invalid_arguments_do_not_connect(self):
        self.assertEqual(self.invoke("--help").returncode, 0)
        self.assertEqual(self.invoke("--unknown").returncode, 2)
        self.assertEqual(self.invoke("--no-connect", "extra").returncode, 2)
        self.assertFalse(self.calls.exists())
