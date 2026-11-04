"""A broken workflow notifies once, and its recovery once more.

Run: uv run python -m unittest discover tests
"""
from __future__ import annotations

import json
import os
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import pipeline_alert as pa  # noqa: E402


class DecideTests(unittest.TestCase):
    def test_a_first_failure_opens_an_alert(self):
        self.assertEqual(pa.decide("failure", None), pa.OPEN)
        self.assertEqual(pa.decide("timed_out", None), pa.OPEN)

    def test_a_repeat_failure_only_updates_it(self):
        self.assertEqual(pa.decide("failure", {"number": 5}), pa.UPDATE)

    def test_success_closes_an_open_alert_and_is_otherwise_silent(self):
        self.assertEqual(pa.decide("success", {"number": 5}), pa.CLOSE)
        self.assertEqual(pa.decide("success", None), pa.NOTHING)

    def test_cancelled_and_skipped_runs_say_nothing(self):
        for conclusion in ("cancelled", "skipped", "neutral"):
            self.assertEqual(pa.decide(conclusion, {"number": 5}), pa.NOTHING)
            self.assertEqual(pa.decide(conclusion, None), pa.NOTHING)


class RunTests(unittest.TestCase):
    def run_alert(self, conclusion, open_alerts):
        calls = []

        def fake_gh(*args):
            calls.append(args)
            if args[:2] == ("issue", "list"):
                return json.dumps(open_alerts)
            if args[:2] == ("run", "view"):
                return "generate\tstep\t2026-11-04T14:00:00Z boom\n"
            return "https://github.com/x/y/issues/9\n"

        env = {
            "WORKFLOW": "publish", "CONCLUSION": conclusion, "RUN_URL": "https://run",
            "RUN_ID": "42", "EVENT": "push", "OWNER": "RaymondRuff",
        }
        with mock.patch.dict(os.environ, env), \
             mock.patch.object(pa, "gh", fake_gh), \
             mock.patch.object(pa.subprocess, "run"):
            pa.main()
        return calls

    def test_open_assigns_the_owner_and_carries_the_log(self):
        calls = self.run_alert("failure", [])
        create = next(c for c in calls if c[:2] == ("issue", "create"))
        self.assertIn("Pipeline failing: publish", create)
        self.assertIn("RaymondRuff", create)
        body = create[create.index("--body") + 1]
        self.assertIn("boom", body)
        self.assertIn("**Failed runs:** 1", body)

    def test_update_counts_and_keeps_the_first_failure(self):
        existing = {
            "number": 9, "title": "Pipeline failing: publish",
            "body": "**First failed:** 2026-11-01 14:00 UTC\n**Failed runs:** 2\n",
        }
        calls = self.run_alert("failure", [existing])
        edit = next(c for c in calls if c[:2] == ("issue", "edit"))
        body = edit[edit.index("--body") + 1]
        self.assertIn("**Failed runs:** 3", body)
        self.assertIn("**First failed:** 2026-11-01 14:00 UTC", body)
        self.assertFalse(any(c[:2] in {("issue", "create"), ("issue", "comment")} for c in calls))

    def test_an_alert_for_another_workflow_is_left_alone(self):
        other = {"number": 3, "title": "Pipeline failing: generate-episode", "body": ""}
        calls = self.run_alert("success", [other])
        self.assertFalse(any(c[:2] == ("issue", "close") for c in calls))

    def test_recovery_comments_and_closes(self):
        existing = {"number": 9, "title": "Pipeline failing: publish", "body": ""}
        calls = self.run_alert("success", [existing])
        self.assertIn(("issue", "close", "9"), calls)


if __name__ == "__main__":
    unittest.main()
