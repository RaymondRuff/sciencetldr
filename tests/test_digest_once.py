"""One email and one episode per digest, however often its file is pushed.

On 2026-11-15 the digest routine committed `digest/2026-11-15.md` at 14:14 and
revised it at 14:16. Both `email-digest` and `monday-podcast` fire on any push
touching `digest/*.md`, so six people received two different digests and the
picker opened two Issues for the same paper — which would have published as two
episodes on consecutive days.

The scout is left free to keep researching. What changed is downstream: the
email waits for Monday morning, and both consumers record what they have
already done rather than inferring it from a diff.

Run: uv run python -m unittest discover tests
"""
from __future__ import annotations

import contextlib
import io
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import email_digest  # noqa: E402
import mailing_list as ml  # noqa: E402
import select_monday_paper as picker  # noqa: E402
import send_email  # noqa: E402

WORKFLOWS = Path(__file__).resolve().parent.parent / ".github" / "workflows"


class OverdueTests(unittest.TestCase):
    """When an unsent digest becomes something to shout about."""

    def at(self, when: str) -> datetime:
        return datetime.fromisoformat(when).replace(tzinfo=timezone.utc)

    def test_a_sunday_digest_is_not_overdue_during_mondays_send_window(self):
        # The crons run 11:50-13:50 UTC Monday; noon Monday is mid-window.
        self.assertFalse(ml.overdue("2026-11-15", now=self.at("2026-11-16T12:00")))

    def test_it_is_overdue_once_monday_has_passed(self):
        self.assertTrue(ml.overdue("2026-11-15", now=self.at("2026-11-17T00:30")))

    def test_a_filename_that_is_not_a_date_is_never_overdue(self):
        self.assertFalse(ml.overdue("draft", now=self.at("2030-01-01T00:00")))


class UnsentTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.digests = Path(self.tmp.name) / "digest"
        self.digests.mkdir()
        for stamp in ("2026-11-01", "2026-11-08", "2026-11-15"):
            (self.digests / f"{stamp}.md").write_text(f"# {stamp}\n")
        patch = mock.patch.object(ml, "DIGEST_DIR", self.digests)
        patch.start()
        self.addCleanup(patch.stop)

    def test_unsent_is_everything_not_on_the_record_oldest_first(self):
        found = ml.unsent_digests({"2026-11-01"})
        self.assertEqual([p.stem for p in found], ["2026-11-08", "2026-11-15"])

    def test_nothing_unsent_is_an_empty_list_not_an_error(self):
        self.assertEqual(ml.unsent_digests({"2026-11-01", "2026-11-08", "2026-11-15"}), [])

    def test_a_missing_digest_directory_is_not_an_error(self):
        with mock.patch.object(ml, "DIGEST_DIR", self.digests / "nope"):
            self.assertEqual(ml.unsent_digests(set()), [])


class SendSelectionTests(unittest.TestCase):
    """A scheduled send takes the newest digest that has not gone out."""

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.digests = Path(self.tmp.name) / "digest"
        self.digests.mkdir()
        for stamp in ("2026-11-08", "2026-11-15"):
            (self.digests / f"{stamp}.md").write_text(f"# Digest {stamp}\n\nA paper.\n")
        for patch in (
            mock.patch.object(ml, "DIGEST_DIR", self.digests),
            mock.patch.dict("os.environ", {"GMAIL_APP_PASSWORD": "x", "DIGEST_FILE": ""}),
        ):
            patch.start()
            self.addCleanup(patch.stop)
        self.recorded: list[str] = []

    def _run(self, sent: set[str]):
        """email_digest.main() with the record and the mail both stubbed."""
        bodies: list[str] = []
        out = io.StringIO()
        with mock.patch.object(ml, "sent_digests", lambda: set(sent)), \
                mock.patch.object(ml, "record_sent", lambda s: self.recorded.append(s) or True), \
                mock.patch.object(ml, "recipients", lambda: ["a@example.com"]), \
                mock.patch.object(send_email, "send", lambda **kw: bodies.append(kw["body_text"])), \
                contextlib.redirect_stdout(out):
            email_digest.main()
        return bodies, out.getvalue()

    def test_the_newest_unsent_digest_is_the_one_sent(self):
        bodies, _ = self._run(sent={"2026-11-08"})
        self.assertIn("Digest 2026-11-15", bodies[0])
        self.assertEqual(self.recorded, ["2026-11-15"])

    def test_an_older_digest_is_picked_up_if_it_was_missed(self):
        # A Monday the schedule never delivered: last week's still goes out.
        bodies, _ = self._run(sent={"2026-11-15"})
        self.assertIn("Digest 2026-11-08", bodies[0])

    def test_with_everything_sent_it_does_nothing_quietly(self):
        bodies, log = self._run(sent={"2026-11-08", "2026-11-15"})
        self.assertEqual(bodies, [])
        self.assertEqual(self.recorded, [])
        self.assertIn("already been emailed", log)


class PickerOnceTests(unittest.TestCase):
    """One episode per digest, so a revised digest does not queue a second."""

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.digest = Path(self.tmp.name) / "2026-11-15.md"
        self.digest.write_text("# Digest\n")
        self.opened: list[str] = []
        self.recorded: list[str] = []
        # These tests are about one-episode-per-digest, not about duplicate
        # detection, so already_seen_dois() is stubbed empty below. Left real
        # it drops this paper — its DOI is a published episode — and main()
        # exits before the part under test.
        self.paper = {
            "title": "A paper about engagers",
            "dice": 4,
            "is_preprint": False,
            "doi": "10.1158/1535-7163.MCT-25-1542",
        }

    def _run(self, picked: set[str], force: bool = False, record=None) -> str:
        plan = picker.PickPlan(chosen=self.paper, pdf_url=None, fetched=None)
        out = io.StringIO()
        env = {"PICK_FORCE": "true"} if force else {"PICK_FORCE": ""}
        with mock.patch.dict("os.environ", env), \
                mock.patch.object(picker.github_issue, "ensure_auth", lambda: None), \
                mock.patch.object(picker, "latest_digest", lambda: self.digest), \
                mock.patch.object(picker, "parse_papers", lambda text: [self.paper]), \
                mock.patch.object(
                    picker.select_friday_paper, "already_seen_dois", set
                ), \
                mock.patch.object(picker, "plan_pick", lambda *a, **k: plan), \
                mock.patch.object(ml, "picked_digests", lambda: set(picked)), \
                mock.patch.object(
                    ml,
                    "record_picked",
                    record or (lambda s: self.recorded.append(s) or True),
                ), \
                mock.patch.object(
                    picker, "open_pick",
                    lambda *a, **k: (self.opened.append(k["title"]) or 131),
                ), \
                contextlib.redirect_stdout(out):
            picker.main()
        return out.getvalue()

    def test_a_digest_not_yet_picked_from_opens_an_issue(self):
        self._run(picked=set())
        self.assertEqual(len(self.opened), 1)
        self.assertEqual(self.recorded, ["2026-11-15"])

    def test_a_second_push_of_the_same_digest_opens_nothing(self):
        log = self._run(picked={"2026-11-15"})
        self.assertEqual(self.opened, [])
        self.assertEqual(self.recorded, [])
        self.assertIn("already been queued", log)

    def test_force_picks_again_on_purpose(self):
        self._run(picked={"2026-11-15"}, force=True)
        self.assertEqual(len(self.opened), 1)

    def test_a_record_that_cannot_be_stored_warns_but_keeps_the_issue(self):
        log = self._run(picked=set(), record=lambda stamp: False)
        self.assertEqual(len(self.opened), 1)
        self.assertIn("WARNING", log)
        self.assertIn("#131", log)


class WatchdogTests(unittest.TestCase):
    """Nothing fails when a Monday send never happens, so this must notice."""

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.digests = Path(self.tmp.name) / "digest"
        self.digests.mkdir()
        (self.digests / "2026-11-01.md").write_text("# Digest\n")
        patch = mock.patch.object(ml, "DIGEST_DIR", self.digests)
        patch.start()
        self.addCleanup(patch.stop)
        self.calls: list[tuple] = []

    def _gh(self, open_titles: list[str]):
        import json as _json

        def run(*args):
            self.calls.append(args)
            if args[:1] == ("api",):
                return ""
            if args[:2] == ("issue", "list"):
                return _json.dumps([{"title": t} for t in open_titles])
            return "https://github.com/owner/repo/issues/999\n"

        return run

    def _pending(self, sent: set[str], open_titles: list[str] = ()) -> str:
        out = io.StringIO()
        with mock.patch.object(ml, "sent_digests", lambda: set(sent)), \
                mock.patch.object(ml, "_gh", self._gh(list(open_titles))), \
                contextlib.redirect_stdout(out):
            ml.pending()
        return out.getvalue()

    def test_an_overdue_digest_opens_one_issue(self):
        log = self._pending(sent=set())
        created = [c for c in self.calls if c[:2] == ("issue", "create")]
        self.assertEqual(len(created), 1)
        self.assertIn("Digest 2026-11-01 has not been emailed", created[0])
        self.assertIn("999", log)

    def test_it_does_not_open_a_second_one(self):
        self._pending(sent=set(), open_titles=["Digest 2026-11-01 has not been emailed"])
        self.assertEqual([c for c in self.calls if c[:2] == ("issue", "create")], [])

    def test_a_digest_already_sent_is_not_chased(self):
        log = self._pending(sent={"2026-11-01"})
        self.assertEqual(self.calls, [])
        self.assertIn("no digest is waiting", log)

    def test_a_digest_still_inside_its_send_window_is_left_alone(self):
        fresh = datetime.now(tz=timezone.utc).date().isoformat()
        (self.digests / f"{fresh}.md").write_text("# Today\n")
        with mock.patch.object(ml, "overdue", lambda stamp, **kw: False):
            log = self._pending(sent=set())
        self.assertEqual(self.calls, [])
        self.assertIn("none past its send window", log)

    def dispatches(self) -> list[tuple]:
        return [c for c in self.calls if c[:1] == ("api",)]

    def test_a_digest_inside_its_send_window_is_not_chased(self):
        # Monday's crons may still deliver; asking now would only race them.
        fresh = (datetime.now(tz=timezone.utc) - timedelta(hours=10)).date().isoformat()
        (self.digests / f"{fresh}.md").write_text("# Fresh\n")
        with mock.patch.object(ml, "sent_digests", lambda: {"2026-11-01"}), \
                mock.patch.object(ml, "_gh", self._gh([])), \
                contextlib.redirect_stdout(io.StringIO()) as out:
            ml.pending()
        self.assertEqual(self.calls, [])
        self.assertIn("none past its send window", out.getvalue())

    def test_once_the_window_closes_it_asks_for_the_send(self):
        # The fix for 2026-11-23: email-digest's own crons were not delivered
        # at all, and this poll's schedule was.
        log = self._pending(sent=set())
        self.assertEqual(len(self.dispatches()), 1)
        call = self.dispatches()[0]
        self.assertIn("-X", call)
        self.assertIn("event_type=digest", call)
        self.assertIn("asked email-digest to run", log)

    def test_asking_comes_before_complaining(self):
        # A digest past its send window but not yet properly overdue is chased
        # and raises no Issue.
        #
        # The thresholds count from midnight of the digest's own date, so
        # "due but not overdue" is the clock window 14:00-24:00 UTC. Deriving
        # a stamp from `now - 40 hours` therefore passed in the afternoon and
        # failed after midnight — which is exactly what it did. The state is
        # named here instead of being inferred from the wall clock.
        due_not_overdue = lambda stamp, hours=ml.OVERDUE_HOURS, now=None: (  # noqa: E731
            hours == ml.DUE_HOURS
        )
        with mock.patch.object(ml, "sent_digests", set), \
                mock.patch.object(ml, "overdue", due_not_overdue), \
                mock.patch.object(ml, "_gh", self._gh([])), \
                contextlib.redirect_stdout(io.StringIO()):
            ml.pending()
        self.assertEqual(len(self.dispatches()), 1)
        self.assertEqual([c for c in self.calls if c[:2] == ("issue", "create")], [])

    def test_a_properly_overdue_digest_is_chased_and_reported(self):
        self._pending(sent=set())
        self.assertEqual(len(self.dispatches()), 1, "still asks")
        self.assertEqual(
            len([c for c in self.calls if c[:2] == ("issue", "create")]), 1, "and shouts"
        )

    def test_the_issue_says_the_send_itself_is_failing(self):
        self._pending(sent=set())
        created = next(c for c in self.calls if c[:2] == ("issue", "create"))
        body = created[created.index("--body") + 1]
        self.assertIn("the send itself is failing", body)

    def test_a_refused_dispatch_is_reported_not_fatal(self):
        def refuse(*args):
            if args[:1] == ("api",):
                raise RuntimeError("403 Forbidden")
            return "[]"

        with mock.patch.object(ml, "sent_digests", set), \
                mock.patch.object(ml, "_gh", refuse), \
                contextlib.redirect_stdout(io.StringIO()) as out:
            ml.pending()   # must not raise
        self.assertIn("could not ask for the digest send", out.getvalue())

    def test_the_watchdog_never_fails_the_poll_that_runs_it(self):
        def boom(*a, **k):
            raise RuntimeError("papers repo unreachable")

        out = io.StringIO()
        with mock.patch.object(ml, "sent_digests", boom), \
                mock.patch.object(sys, "argv", ["mailing_list.py", "pending"]), \
                contextlib.redirect_stdout(out):
            ml.main()   # must not raise
        self.assertIn("WARNING", out.getvalue())


class WorkflowShapeTests(unittest.TestCase):
    def text(self, name: str) -> str:
        return (WORKFLOWS / name).read_text(encoding="utf-8")

    def test_the_digest_send_no_longer_fires_on_a_push(self):
        # The whole point: the scout may commit as often as it likes.
        body = self.text("email-digest.yml").split("jobs:", 1)[0]
        self.assertNotIn("push:", body)
        self.assertIn("workflow_dispatch:", body)

    def test_it_has_several_monday_morning_chances(self):
        crons = [
            line.split("'")[1]
            for line in self.text("email-digest.yml").splitlines()
            if "- cron:" in line
        ]
        self.assertGreaterEqual(len(crons), 2, "one dropped cron should not skip a week")
        for cron in crons:
            with self.subTest(cron=cron):
                self.assertTrue(cron.endswith(" * * 1"), "Monday only")
                hour = int(cron.split()[1])
                # After the episode publishes (~11:25 UTC) and before 6am
                # Pacific, which is 14:00 UTC in winter.
                self.assertGreaterEqual(hour, 11)
                self.assertLess(hour, 14)

    def test_the_poll_watches_for_a_digest_that_never_went_out(self):
        self.assertIn("mailing_list.py pending", self.text("mailing-list.yml"))


if __name__ == "__main__":
    unittest.main()
