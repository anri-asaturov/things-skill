"""Exercise the CLI without launching osascript or reading real task data."""

import contextlib
import datetime as dt
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import unittest
from unittest import mock


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "things.py"
SPEC = importlib.util.spec_from_file_location("things", SCRIPT)
things = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(things)


class ValidationTests(unittest.TestCase):
    def test_rejects_malformed_or_unsupported_requests(self):
        invalid = [
            [], None, {}, {"op": []}, {"op": "delete"},
            {"op": "create", "title": " "},
            {"op": "create", "title": "Task\x00"},
            {"op": "create", "title": "Task", "reminder": "tomorrow"},
            {"op": "update", "id": "task-1"},
            {"op": "update", "title": "Task"},
            {"op": "complete"}, {"op": "get", "id": 1},
            {"op": "search", "query": " "},
            {"op": "list", "list": "Inbox", "project_id": "project-1"},
            {"op": "list", "area_id": "area-1", "project_id": "project-1"},
            {"op": "list", "status": "deleted"},
            {"op": "list", "include_notes": "false"},
            {"op": "list", "limit": True}, {"op": "list", "limit": 0},
            {"op": "list", "limit": 201}, {"op": "list", "offset": -1},
            {"op": "list", "offset": 1.5},
            {"op": "create-project", "title": "Project", "project_id": "project-1"},
            {"op": "update", "id": "task-1", "when": "2026-02-30"},
            {"op": "update", "id": "task-1", "deadline": "tomorrow"},
            {"op": "update", "id": "task-1", "when": None},
            {"op": "update", "id": "task-1", "tags": "Work"},
            {"op": "update", "id": "task-1", "tags": ["Work", "Work"]},
            {"op": "update", "id": "task-1", "tags": ["Work,Home"]},
            {"op": "update", "id": "task-1", "tags": [""]},
            {"op": "complete", "id": "task-1", "expected_modified": "2026-10-04T12:00:00"},
            {"op": "complete", "id": "task-1", "expected_modified": "not-a-date"},
        ]
        for request in invalid:
            with self.subTest(request=request), self.assertRaises(ValueError):
                things.validate(request)

    def test_defaults_limit_disclosure_and_do_not_mutate_input(self):
        request = {"op": "list"}
        result = things.validate(request)
        self.assertEqual(request, {"op": "list"})
        self.assertEqual(result["limit"], 30)
        self.assertEqual(result["offset"], 0)
        self.assertFalse(result["include_notes"])
        self.assertTrue(things.validate({"op": "get", "id": "task-1"})["include_notes"])

    def test_relative_dates_use_calendar_arithmetic_across_year_boundary(self):
        class FixedDate(dt.date):
            @classmethod
            def today(cls):
                return cls(2026, 12, 31)

        with mock.patch.object(things.dt, "date", FixedDate):
            for when, expected in (("today", "2026-12-31"), ("tomorrow", "2027-01-01")):
                result = things.validate({"op": "create", "title": "Task", "when": when})
                self.assertEqual(result["when"], expected)

    def test_explicit_clearing_is_preserved_and_omitted_fields_stay_absent(self):
        request = {"op": "update", "id": "task-1", "notes": "", "tags": [], "deadline": None}
        result = things.validate(request)
        self.assertEqual(result, request)
        self.assertNotIn("when", result)


class CLITests(unittest.TestCase):
    def invoke(self, *args, request=None, stdout='{"ok": true}', stderr="", returncode=0, error=None):
        output = io.StringIO()
        result = subprocess.CompletedProcess([], returncode, stdout, stderr)
        with mock.patch.object(things.sys, "argv", [str(SCRIPT), *args]), \
                mock.patch.object(things.sys, "stdin", io.StringIO(json.dumps(request))), \
                mock.patch.object(things.subprocess, "run", return_value=result, side_effect=error) as run, \
                contextlib.redirect_stdout(output):
            code = things.main()
        return code, json.loads(output.getvalue()), run

    def test_validate_only_never_connects_even_with_apply(self):
        code, result, run = self.invoke(
            "request", "--apply", "--validate-only", request={"op": "create", "title": "Task"}
        )
        self.assertEqual(code, 0)
        self.assertTrue(result["validated"])
        self.assertFalse(result["connected"])
        run.assert_not_called()

    def test_invalid_request_is_rejected_before_connecting(self):
        code, result, run = self.invoke("request", "--apply", request={"op": "complete"})
        self.assertEqual(code, 1)
        self.assertFalse(result["write_may_have_applied"])
        run.assert_not_called()

    def test_mixed_json_and_flags_are_rejected(self):
        code, result, run = self.invoke("request", "--limit", "10", request={"op": "list"})
        self.assertEqual(code, 1)
        self.assertIn("rather than mixing", result["error"])
        run.assert_not_called()

    def test_task_text_is_a_json_argument_and_writes_default_to_preview(self):
        title = 'Buy café supplies; $(touch /tmp/not-executed) "quoted"\nNext line'
        code, _, run = self.invoke("request", request={"op": "create", "title": title})
        self.assertEqual(code, 0)
        command = run.call_args.args[0]
        self.assertEqual(command[:3], ["/usr/bin/osascript", "-l", "JavaScript"])
        self.assertEqual(Path(command[3]), SCRIPT.with_suffix(".js"))
        self.assertEqual(len(command), 5)
        self.assertEqual(json.loads(command[4]), {"op": "create", "title": title, "apply": False})
        self.assertFalse(run.call_args.kwargs.get("shell", False))
        self.assertEqual(run.call_args.kwargs["timeout"], 60)

    def test_today_alias_and_pagination_reach_bridge(self):
        _, _, run = self.invoke("today", "--limit", "20", "--offset", "40")
        request = json.loads(run.call_args.args[0][-1])
        self.assertEqual((request["op"], request["list"]), ("list", "Today"))
        self.assertEqual((request["limit"], request["offset"]), (20, 40))

    def test_timeout_marks_only_applied_writes_uncertain_and_does_not_retry(self):
        for flags, expected in (((), False), (("--apply",), True)):
            with self.subTest(flags=flags):
                code, result, run = self.invoke(
                    "request", *flags, request={"op": "create", "title": "Task"},
                    error=subprocess.TimeoutExpired("osascript", 60),
                )
                self.assertEqual(code, 1)
                self.assertEqual(result["write_may_have_applied"], expected)
                run.assert_called_once()

    def test_verification_failure_is_preserved_and_returns_failure(self):
        response = {"ok": False, "applied": True, "verified": False, "mismatches": ["when"]}
        code, result, run = self.invoke(
            "request", "--apply", request={"op": "update", "id": "task-1", "when": "someday"},
            stdout=json.dumps(response),
        )
        self.assertEqual(code, 1)
        self.assertEqual(result, response)
        run.assert_called_once()

    def test_automation_denial_has_actionable_error(self):
        code, result, _ = self.invoke("status", stderr="Not authorized (-1743)", returncode=1)
        self.assertEqual(code, 1)
        self.assertIn("Privacy & Security > Automation", result["error"])
        self.assertFalse(result["write_may_have_applied"])

    def test_invalid_bridge_output_after_apply_is_reported_as_uncertain(self):
        code, result, run = self.invoke(
            "request", "--apply", request={"op": "create", "title": "Task"}, stdout="invalid JSON",
        )
        self.assertEqual(code, 1)
        self.assertTrue(result["write_may_have_applied"])
        run.assert_called_once()


if __name__ == "__main__":
    unittest.main()
