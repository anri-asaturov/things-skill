#!/usr/bin/env python3
"""Small JSON CLI for Things' supported macOS scripting interface."""

import argparse
import datetime as dt
import json
from pathlib import Path
import re
import subprocess
import sys


READS = {"status", "lists", "list", "get", "search", "projects", "areas", "tags"}
WRITES = {"create", "create-project", "update", "complete", "cancel", "reopen"}
FIELDS = {"title", "notes", "tags", "when", "deadline", "project_id", "area_id"}
FILTERS = {"list", "project_id", "area_id", "query", "status", "tag", "limit", "offset", "include_notes"}
ALLOWED = {
    "status": set(), "lists": set(), "areas": {"limit", "offset"},
    "tags": {"limit", "offset"}, "list": FILTERS,
    "search": FILTERS, "projects": {"status", "area_id", "limit", "offset", "include_notes"},
    "get": {"id", "include_notes"},
    "create": FIELDS, "create-project": FIELDS - {"project_id"},
    "update": FIELDS | {"id", "expected_modified"},
    "complete": {"id", "expected_modified"}, "cancel": {"id", "expected_modified"},
    "reopen": {"id", "expected_modified"},
}


def validate(request):
    if not isinstance(request, dict):
        raise ValueError("The request must be one JSON object.")
    request = dict(request)
    op = request.get("op")
    if not isinstance(op, str) or op not in ALLOWED:
        raise ValueError("Unknown op. Choose: " + ", ".join(sorted(ALLOWED)))
    unknown = set(request) - ALLOWED[op] - {"op"}
    if unknown:
        raise ValueError("Unsupported fields for this op: " + ", ".join(sorted(unknown)))
    for key in {"id", "project_id", "area_id", "title", "notes", "list", "query", "status", "tag", "when", "expected_modified"} & set(request):
        value = request[key]
        if not isinstance(value, str) or "\x00" in value:
            raise ValueError(key + " must be a string without NUL characters.")
        if key != "notes" and not value.strip():
            raise ValueError(key + " cannot be empty.")
    if "project_id" in request and "area_id" in request:
        raise ValueError("Specify either project_id or area_id; a project's area is inherited.")
    if op in {"list", "search"} and sum(key in request for key in ("list", "project_id", "area_id")) > 1:
        raise ValueError("Use only one list, project_id, or area_id scope.")
    if "expected_modified" in request:
        parsed = dt.datetime.fromisoformat(request["expected_modified"].replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            raise ValueError("expected_modified must include a timezone, as returned by get.")
    if op in {"get", "update", "complete", "cancel", "reopen"} and not request.get("id"):
        raise ValueError("This operation requires an exact id from a read result.")
    if op.startswith("create") and not request.get("title", "").strip():
        raise ValueError("Creating an item requires a title.")
    if op == "search" and not request.get("query", "").strip():
        raise ValueError("Search requires query.")
    if op == "update" and not (FIELDS & set(request)):
        raise ValueError("Update requires at least one field to change.")
    if "status" in request and request["status"] not in {"open", "completed", "canceled", "all"}:
        raise ValueError("status must be open, completed, canceled, or all.")
    if "tags" in request:
        tags = request["tags"]
        if not isinstance(tags, list) or any(not isinstance(t, str) or not t.strip() or "," in t or "\x00" in t for t in tags):
            raise ValueError("tags must be an array of nonempty tag names without commas or NULs.")
        if len(tags) != len(set(tags)):
            raise ValueError("Duplicate tags are not allowed.")
    for key in ("when", "deadline"):
        if key not in request:
            continue
        value = request[key]
        if key == "when" and value in {"today", "tomorrow"}:
            # Use local calendar arithmetic across daylight-saving changes.
            request[key] = (dt.date.today() + dt.timedelta(days=value == "tomorrow")).isoformat()
            continue
        if key == "when" and value in {"anytime", "someday"}:
            continue
        if key == "deadline" and value is None:
            continue
        if not isinstance(value, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
            raise ValueError(key + " must be YYYY-MM-DD" + (" or null to clear it." if key == "deadline" else ", today, tomorrow, anytime, or someday."))
        dt.date.fromisoformat(value)
    for key, default in (("limit", 30), ("offset", 0)):
        if key in ALLOWED[op]:
            request.setdefault(key, default)
            value = request[key]
            if isinstance(value, bool) or not isinstance(value, int) or value < (1 if key == "limit" else 0):
                raise ValueError(key + " must be a positive integer." if key == "limit" else "offset must be a nonnegative integer.")
            if key == "limit" and value > 200:
                raise ValueError("limit cannot exceed 200; use offset to paginate.")
    if "include_notes" in ALLOWED[op]:
        request.setdefault("include_notes", op == "get")
        if not isinstance(request["include_notes"], bool):
            raise ValueError("include_notes must be a boolean.")
    return request


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("operation", choices=sorted(READS) + ["today", "inbox", "request"])
    parser.add_argument("--id")
    parser.add_argument("--list")
    parser.add_argument("--query")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--offset", type=int)
    parser.add_argument("--include-notes", action="store_true", default=None)
    parser.add_argument("--file", help="JSON request file for request; otherwise read JSON from stdin")
    parser.add_argument("--apply", action="store_true", help="Execute an authorized write; default is a preview")
    parser.add_argument("--validate-only", action="store_true", help="Validate input without connecting to Things")
    args = parser.parse_args()
    is_write = False
    try:
        if args.operation == "request":
            request = json.loads(Path(args.file).read_text() if args.file else sys.stdin.read())
            if any(getattr(args, key) is not None for key in ("id", "list", "query", "limit", "offset", "include_notes")):
                raise ValueError("Put request fields in JSON, rather than mixing JSON and flags.")
        else:
            if args.file:
                raise ValueError("--file is only valid with request.")
            request = {"op": args.operation}
            if args.operation in {"today", "inbox"}:
                request = {"op": "list", "list": args.operation.title()}
            request.update({key: getattr(args, key) for key in ("id", "list", "query", "limit", "offset", "include_notes") if getattr(args, key) is not None})
        request = validate(request)
        is_write = request["op"] in WRITES and args.apply
        if args.validate_only:
            result = {"ok": True, "validated": True, "request": request, "connected": False}
        else:
            request["apply"] = args.apply
            bridge = Path(__file__).resolve().with_name("things.js")
            proc = subprocess.run(
                ["/usr/bin/osascript", "-l", "JavaScript", str(bridge), json.dumps(request, ensure_ascii=False)],
                text=True, capture_output=True, timeout=60, check=False,
            )
            if proc.returncode:
                detail = proc.stderr.strip()
                if "-1743" in detail or "not author" in detail.lower():
                    raise RuntimeError("macOS Automation access is denied. In System Settings > Privacy & Security > Automation, enable Things under the app running this command (usually Codex).")
                if "Connection invalid" in detail or "Connection Invalid" in detail:
                    raise RuntimeError("The shell sandbox cannot reach macOS Automation. Run this same helper through an approved host/sandbox escalation; do not change macOS security settings to work around it.")
                raise RuntimeError(detail or "osascript failed without an error message.")
            result = json.loads(proc.stdout)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if result.get("ok") else 1
    except subprocess.TimeoutExpired:
        result = {"ok": False, "error": "Things did not respond within 60 seconds.", "write_may_have_applied": is_write}
    except (ValueError, OSError, RuntimeError) as error:
        result = {"ok": False, "error": str(error), "write_may_have_applied": is_write}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 1


if __name__ == "__main__":
    sys.exit(main())
