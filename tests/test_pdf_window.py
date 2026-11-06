"""A paywalled top pick gets one ask, a deadline, and an honest fallback.

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

import paper_text  # noqa: E402
import pdf_mailbox  # noqa: E402
import pdf_window as pw  # noqa: E402
import routine_tools  # noqa: E402
import select_friday_paper  # noqa: E402
import select_monday_paper as monday  # noqa: E402

TEXT = paper_text.Fetched("full text " * 3000, "europepmc:PMC9")
RUNNER = {"title": "The runner-up", "doi": "10.1/runner", "dice": 4, "raw": "excerpt",
          "pdf_url": "https://oa/runner.pdf"}


def at(text):
    return pw.parse_iso(text)


class DeadlineTests(unittest.TestCase):
    def test_monday_morning_in_winter_runs_to_9pm_pacific(self):
        # The digest routine runs at 06:00 Pacific; its pick lands around 06:30.
        deadline = pw.deadline_for(at("2026-11-09T14:30:00Z"))
        self.assertEqual(pw.iso(deadline), "2026-11-10T05:00:00Z")
        self.assertEqual(pw.describe(deadline), "9:00 pm Pacific on Mon 9 Nov (05:00 UTC)")

    def test_friday_in_summer_runs_to_9pm_daylight_time(self):
        # friday-podcast runs at 11:00 UTC, which is 04:00 Pacific in July.
        deadline = pw.deadline_for(at("2026-07-10T11:00:00Z"))
        self.assertEqual(pw.iso(deadline), "2026-07-11T04:00:00Z")

    def test_both_deadlines_close_before_the_writer_runs(self):
        for picked in ("2026-11-09T14:30:00Z", "2026-07-10T11:00:00Z", "2026-03-06T12:00:00Z"):
            deadline = pw.deadline_for(at(picked))
            self.assertLess(deadline.hour, 8, picked)  # the writer starts at 08:00 UTC

    def test_a_pick_late_in_the_day_gets_until_tomorrow_evening(self):
        # 17:00 Pacific: 9 pm is only four hours away.
        deadline = pw.deadline_for(at("2026-11-10T01:00:00Z"))
        self.assertEqual(pw.iso(deadline), "2026-11-11T05:00:00Z")

    def test_unreadable_deadlines_are_none_not_errors(self):
        self.assertIsNone(pw.parse_iso("next tuesday"))
        self.assertIsNone(pw.parse_iso(None))


def windowed_issue(number=43, *, runner=RUNNER, deadline="2026-11-10T05:00:00Z",
                   source="monday-digest", labels=("needs-pdf", "pdf-requested", "awaiting-pdf")):
    meta = {"title": "The top pick", "doi": "10.1/top", "source": source,
            "pdf_deadline": deadline, "runner_up": runner}
    body = "<!-- METADATA -->\n```json\n" + json.dumps(meta) + "\n```\n<!-- /METADATA -->"
    return {"number": number, "title": "📄 The top pick", "body": body,
            "labels": [{"name": n} for n in ("podcast-pending", source, *labels)]}


class ResolveTests(unittest.TestCase):
    def setUp(self):
        self.calls = []
        self.fetch_result = ("https://oa/runner.pdf", TEXT)
        patches = [
            mock.patch.object(pw.github_issue, "comment", lambda n, b: self.calls.append(("comment", n, b))),
            mock.patch.object(pw.github_issue, "remove_label", lambda n, l: self.calls.append(("unlabel", n, l))),
            mock.patch.object(pw.github_issue, "open_issue", self.open_issue),
            mock.patch.object(monday, "obtain", self.obtain),
            mock.patch.object(monday, "stage_for_writer", lambda n, p, f, journal="": self.calls.append(("stage", n, p["doi"]))),
            mock.patch.object(select_friday_paper, "already_seen_dois", lambda: {"10.1/top"}),
        ]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)

    def open_issue(self, *, title, body, labels):
        self.calls.append(("open", title, tuple(labels), body))
        return 101

    def obtain(self, paper):
        if isinstance(self.fetch_result, Exception):
            raise self.fetch_result
        return self.fetch_result

    def kinds(self):
        return [c[0] for c in self.calls]

    def test_nothing_happens_before_the_deadline(self):
        errors = pw.resolve([windowed_issue()], {}, now=at("2026-11-10T04:59:00Z"))
        self.assertEqual((errors, self.calls), ([], []))

    def test_a_pdf_that_arrived_in_time_wins(self):
        # Staging already cleared its labels; the window has nothing to do.
        pw.resolve([windowed_issue()], {43: {}}, now=at("2026-11-10T06:00:00Z"))
        self.assertEqual(self.calls, [])

    def test_at_the_deadline_the_runner_up_takes_the_slot(self):
        pw.resolve([windowed_issue()], {}, now=at("2026-11-10T05:17:00Z"))
        opened = next(c for c in self.calls if c[0] == "open")
        self.assertEqual(opened[1], "📄 The runner-up")
        self.assertEqual(opened[2], ("podcast-pending", "monday-digest"))
        self.assertIn("Stands in for #43", opened[3])
        self.assertIn(("stage", 101, "10.1/runner"), self.calls)
        note = next(c for c in self.calls if c[0] == "comment")
        self.assertEqual(note[1], 43)
        self.assertIn("#101 stands in", note[2])
        self.assertIn("if the PDF still arrives", note[2])
        # The original stays open and keeps needs-pdf; only the window closes.
        self.assertEqual([c for c in self.calls if c[0] == "unlabel"], [("unlabel", 43, "awaiting-pdf")])

    def test_friday_stand_ins_keep_their_series(self):
        pw.resolve([windowed_issue(source="friday-reddit")], {}, now=at("2026-11-10T06:00:00Z"))
        opened = next(c for c in self.calls if c[0] == "open")
        self.assertTrue(opened[1].startswith("🔥 "))
        self.assertIn("friday-reddit", opened[2])

    def test_with_no_runner_up_the_slot_is_skipped(self):
        pw.resolve([windowed_issue(runner=None)], {}, now=at("2026-11-10T06:00:00Z"))
        self.assertNotIn("open", self.kinds())
        note = next(c for c in self.calls if c[0] == "comment")
        self.assertIn("this slot is skipped rather than filled with a weaker paper", note[2])
        self.assertIn(("unlabel", 43, "awaiting-pdf"), self.calls)

    def test_a_candidate_unchecked_at_pick_time_and_ranked_higher_goes_first(self):
        higher = {"title": "Ranked above", "doi": "10.1/higher", "dice": 5}
        issue = windowed_issue()
        meta_body = issue["body"].replace('"runner_up"', '"stand_ins": %s, "runner_up"' % json.dumps([higher, RUNNER]))
        issue["body"] = meta_body
        pw.resolve([issue], {}, now=at("2026-11-10T06:00:00Z"))
        opened = next(c for c in self.calls if c[0] == "open")
        self.assertEqual(opened[1], "📄 Ranked above")

    def test_a_stand_in_that_is_down_again_is_passed_over(self):
        higher = {"title": "Ranked above", "doi": "10.1/higher", "dice": 5}
        issue = windowed_issue()
        issue["body"] = issue["body"].replace('"runner_up"', '"stand_ins": %s, "runner_up"' % json.dumps([higher, RUNNER]))

        def obtain(p):
            if p["doi"] == "10.1/higher":
                raise paper_text.TransientFetchError("still down")
            return ("https://oa/runner.pdf", TEXT)

        with mock.patch.object(monday, "obtain", obtain):
            pw.resolve([issue], {}, now=at("2026-11-10T06:00:00Z"))
        opened = next(c for c in self.calls if c[0] == "open")
        self.assertEqual(opened[1], "📄 The runner-up")

    def test_when_nothing_could_be_checked_at_all_the_window_waits(self):
        # Every source down at pick time, and again at the deadline: that is an
        # outage, not a paywall, so the slot is not given up.
        unchecked = [{"title": "Unchecked", "doi": "10.1/u", "dice": 5}]
        issue = windowed_issue(runner=None)
        issue["body"] = issue["body"].replace('"runner_up"', '"stand_ins": %s, "runner_up"' % json.dumps(unchecked))
        self.fetch_result = paper_text.TransientFetchError("down")
        pw.resolve([issue], {}, now=at("2026-11-10T06:00:00Z"))
        self.assertEqual(self.calls, [])

    def test_a_runner_up_whose_source_is_down_is_retried_not_dropped(self):
        self.fetch_result = paper_text.TransientFetchError("timeout")
        pw.resolve([windowed_issue()], {}, now=at("2026-11-10T06:00:00Z"))
        self.assertEqual(self.calls, [])  # the window stays open for the next sweep

    def test_a_runner_up_already_queued_is_not_opened_twice(self):
        runner = dict(RUNNER, doi="10.1/top")
        pw.resolve([windowed_issue(runner=runner)], {}, now=at("2026-11-10T06:00:00Z"))
        self.assertNotIn("open", self.kinds())
        self.assertIn(("unlabel", 43, "awaiting-pdf"), self.calls)

    def test_issues_without_a_window_are_ignored(self):
        plain = windowed_issue(labels=("needs-pdf", "pdf-requested"))
        pw.resolve([plain], {}, now=at("2026-12-01T00:00:00Z"))
        self.assertEqual(self.calls, [])

    def test_one_failure_is_reported_and_does_not_stop_the_rest(self):
        def broken(*, title, body, labels):
            raise RuntimeError("gh is down")

        with mock.patch.object(pw.github_issue, "open_issue", broken):
            errors = pw.resolve(
                [windowed_issue(43), windowed_issue(44, runner=None)], {},
                now=at("2026-11-10T06:00:00Z"),
            )
        self.assertEqual(len(errors), 1)
        self.assertIn("#43", errors[0])
        self.assertIn(("unlabel", 44, "awaiting-pdf"), self.calls)


class OpenPickTests(unittest.TestCase):
    def test_a_window_is_labelled_asked_for_once_and_not_staged(self):
        calls = []
        plan = monday.PickPlan(
            {"title": "The top pick", "doi": "10.1/top", "dice": 5, "raw": ""}, None, None,
            window=True, runner_up=dict(RUNNER), runner_up_url="https://oa/runner.pdf",
        )
        with mock.patch.object(monday.github_issue, "open_issue",
                               lambda *, title, body, labels: calls.append(("open", labels)) or 43), \
             mock.patch.object(monday.github_issue, "add_labels",
                               lambda n, labels: calls.append(("label", n, labels))), \
             mock.patch.object(pdf_mailbox, "request",
                               lambda n, **kw: calls.append(("email", n, kw)) or True), \
             mock.patch.object(monday, "stage_for_writer",
                               lambda *a, **k: calls.append(("stage",))):
            monday.open_pick(plan, source="monday-digest", title="📄 The top pick",
                             labels=["podcast-pending", "monday-digest"])
        self.assertIn("awaiting-pdf", calls[0][1])
        self.assertIn("needs-pdf", calls[0][1])
        email = next(c for c in calls if c[0] == "email")
        self.assertIn("9:00 pm Pacific", email[2]["deadline"])
        self.assertEqual(email[2]["runner_up"], "The runner-up")
        self.assertIn(("label", 43, ["pdf-requested"]), calls)
        self.assertNotIn(("stage",), calls)


class EmailTests(unittest.TestCase):
    def send(self, **kwargs):
        sent = {}
        env = {"PDF_REQUEST_TO": "ray@example.com", "GMAIL_APP_PASSWORD": "x"}
        with mock.patch.dict(os.environ, env), \
             mock.patch.object(pdf_mailbox.send_email, "send",
                               lambda **kw: sent.update(kw)):
            pdf_mailbox.request(43, title="The top pick", doi="10.1/top", journal="Cell", **kwargs)
        return sent

    def test_the_ask_names_the_deadline_and_the_runner_up(self):
        sent = self.send(deadline="9:00 pm Pacific on Mon 9 Nov (05:00 UTC)",
                         runner_up="The runner-up")
        self.assertEqual(sent["subject"], "[Science TLDR #43] PDF wanted by 9:00 pm Pacific: The top pick")
        self.assertIn("wanted by\n9:00 pm Pacific on Mon 9 Nov (05:00 UTC)", sent["body_text"])
        self.assertIn("The runner-up", sent["body_text"])
        self.assertIn("if it is good enough there is nothing to do", sent["body_text"])
        self.assertIsNotNone(pdf_mailbox.SUBJECT_RE.search(sent["subject"]))  # replies still match

    def test_without_a_runner_up_it_says_the_slot_is_skipped(self):
        sent = self.send(deadline="9:00 pm Pacific on Mon 9 Nov (05:00 UTC)")
        self.assertIn("the slot is skipped", sent["body_text"])

    def test_a_plain_request_is_unchanged(self):
        sent = self.send()
        self.assertEqual(sent["subject"], "[Science TLDR #43] PDF needed: The top pick")


class QueueTests(unittest.TestCase):
    def test_the_writer_leaves_an_open_window_alone(self):
        issue = {"number": 43, "created_at": "2026-11-09T14:30:00Z",
                 "labels": [{"name": n} for n in ("podcast-pending", "needs-pdf", "awaiting-pdf")]}
        order, skipped = routine_tools.rank_queue([issue], scripts_on_main=set(), branches=[], bundled=set())
        self.assertEqual(order, [])
        self.assertIn("window is open", skipped[0][1])

    def test_a_pdf_that_arrived_in_the_window_is_written_at_once(self):
        issue = {"number": 43, "created_at": "2026-11-09T14:30:00Z",
                 "labels": [{"name": n} for n in ("podcast-pending", "needs-pdf", "awaiting-pdf")]}
        order, _ = routine_tools.rank_queue([issue], scripts_on_main=set(), branches=[], bundled={43})
        self.assertEqual(order, [43])


if __name__ == "__main__":
    unittest.main()
