"""Measuring how many scheduled runs GitHub actually starts.

The numbers this produces are the evidence for every latency claim the README
makes, so the arithmetic is worth pinning: an expected-tick count that is
quietly wrong would turn a broken scheduler into a healthy-looking report.

Nothing here touches the network — `report()` takes its fetcher as an argument.

Run: uv run python -m unittest discover tests
"""
from __future__ import annotations

import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import schedule_health as sh  # noqa: E402

DAY = timedelta(days=1)
NOON = datetime(2026, 11, 14, 12, 0, tzinfo=timezone.utc)  # a Saturday


class ExpectedTickTests(unittest.TestCase):
    def ticks(self, cron: str, days: int = 1) -> int:
        return sh.expected(cron, NOON - days * DAY, NOON)

    def test_a_list_of_minutes(self):
        self.assertEqual(self.ticks("13,43 * * * *"), 48)
        self.assertEqual(self.ticks("9,24,39,54 * * * *"), 96)

    def test_a_step(self):
        self.assertEqual(self.ticks("*/30 * * * *"), 48)
        self.assertEqual(self.ticks("*/15 * * * *"), 96)

    def test_a_range_and_a_step_together(self):
        # Business-hours polling, which this repo does not use but a future
        # one might; the old minute parser crashed on a range.
        self.assertEqual(self.ticks("0 9-17 * * *"), 9)
        self.assertEqual(self.ticks("0 0-23/6 * * *"), 4)

    def test_a_daily_cron(self):
        self.assertEqual(self.ticks("11 14 * * *"), 1)
        self.assertEqual(self.ticks("17 5 * * *"), 1)
        self.assertEqual(self.ticks("11 14 * * *", days=14), 14)

    def test_a_weekly_cron_counts_only_its_weekday(self):
        # 8:11 on Thursdays. The window ends Saturday noon.
        self.assertEqual(self.ticks("8 11 * * 4"), 0)
        self.assertEqual(self.ticks("8 11 * * 4", days=7), 1)
        self.assertEqual(self.ticks("8 11 * * 4", days=28), 4)

    def test_sunday_is_both_zero_and_seven(self):
        self.assertEqual(sh.expected("0 12 * * 0", NOON, NOON + 7 * DAY), 1)
        self.assertEqual(sh.expected("0 12 * * 7", NOON, NOON + 7 * DAY), 1)

    def test_day_of_month_and_weekday_are_ored_not_anded(self):
        # Standard cron: with both restricted, either one matching fires.
        # Nov 2026: the 1st is a Sunday, and there are 4 Thursdays after the 14th.
        both = sh.expected("0 12 1 * 4", datetime(2026, 11, 1, tzinfo=timezone.utc),
                           datetime(2026, 12, 1, tzinfo=timezone.utc))
        self.assertEqual(both, 5)

    def test_a_malformed_cron_is_refused(self):
        with self.assertRaises(ValueError):
            sh.expected("not a cron", NOON - DAY, NOON)
        with self.assertRaises(ValueError):
            sh.expected("* * * *", NOON - DAY, NOON)


class GapTests(unittest.TestCase):
    def test_gaps_are_hours_between_consecutive_runs(self):
        stamps = [NOON, NOON + timedelta(hours=3), NOON + timedelta(hours=4)]
        self.assertEqual(sh.gaps_hours(stamps), [3.0, 1.0])

    def test_gaps_do_not_depend_on_the_order_fetched(self):
        stamps = [NOON + timedelta(hours=4), NOON, NOON + timedelta(hours=3)]
        self.assertEqual(sh.gaps_hours(stamps), [3.0, 1.0])

    def test_one_run_has_no_gaps(self):
        self.assertEqual(sh.gaps_hours([NOON]), [])
        self.assertEqual(sh.percentile([], 0.5), 0.0)


class ReportTests(unittest.TestCase):
    """The shape of the answer, against a known delivery pattern."""

    def fake_fetch(self, delivered: int):
        # Relative to now, because report() windows on the real clock.
        now = datetime.now(tz=timezone.utc)

        def fetch(repo, workflow):
            if workflow != "generate-episode.yml":
                return []
            # Spread `delivered` runs evenly over the last 24 hours.
            step = timedelta(hours=24 / max(delivered, 1))
            return [now - timedelta(hours=24) + step * n for n in range(1, delivered + 1)]
        return fetch

    def report(self, delivered: int) -> dict:
        return sh.report("owner/repo", 1, fetch=self.fake_fetch(delivered))

    def row(self, data: dict, name: str = "generate-episode.yml") -> dict:
        return next(r for r in data["workflows"] if r["workflow"] == name)

    def test_it_only_reports_workflows_that_have_crons(self):
        data = self.report(6)
        named = {r["workflow"] for r in data["workflows"]}
        self.assertIn("generate-episode.yml", named)
        self.assertNotIn("publish.yml", named)  # push-triggered, no cron

    def ticks_asked_for(self) -> int:
        """What generate-episode's real crons ask for in a day.

        Derived, not hard-coded: this test used to assert 51, and pulling the
        half-hourly poll out of that workflow broke it for the right reason.
        """
        now = datetime.now(tz=timezone.utc)
        return sum(
            sh.expected(cron, now - DAY, now)
            for cron in sh.crons_in(sh.WORKFLOWS / "generate-episode.yml")
        )

    def test_the_delivery_rate_is_runs_over_ticks_asked_for(self):
        wanted = self.ticks_asked_for()
        row = self.row(self.report(6))
        self.assertEqual(row["expected"], wanted)
        self.assertEqual(row["delivered"], 6)
        self.assertAlmostEqual(row["rate"], 6 / wanted, places=4)
        self.assertAlmostEqual(row["per_day"], 6.0)

    def test_a_workflow_with_no_runs_reads_zero_not_an_error(self):
        row = self.row(sh.report("owner/repo", 1, fetch=lambda r, w: []))
        self.assertEqual((row["delivered"], row["rate"], row["max_gap"]), (0, 0.0, 0.0))

    def test_the_gap_is_the_latency_a_waiting_email_sees(self):
        # Six runs a day is a four-hour gap, whatever the cron claims.
        row = self.row(self.report(6))
        self.assertAlmostEqual(row["median_gap"], 4.0, places=3)
        self.assertAlmostEqual(row["max_gap"], 4.0, places=3)

    def test_both_renderings_carry_the_numbers(self):
        data = self.report(6)
        rate = f"{6 / self.ticks_asked_for():.1%}"
        for text in (sh.as_text(data), sh.as_markdown(data)):
            self.assertIn("generate-episode.yml", text)
            self.assertIn(rate, text)
        self.assertIn("| workflow |", sh.as_markdown(data))

    def test_runs_outside_the_window_are_not_counted(self):
        stale = lambda repo, workflow: [  # noqa: E731
            datetime.now(tz=timezone.utc) - timedelta(days=30)
        ]
        row = self.row(sh.report("owner/repo", 1, fetch=stale))
        self.assertEqual(row["delivered"], 0)


class FetchTests(unittest.TestCase):
    """A workflow GitHub has not seen yet must not break the measurement."""

    def _gh(self, returncode: int, stdout: str = "", stderr: str = ""):
        class Result:
            pass

        result = Result()
        result.returncode, result.stdout, result.stderr = returncode, stdout, stderr
        return lambda *a, **k: result

    def test_a_404_counts_as_no_runs(self):
        # True of any workflow added on a branch before it reaches main —
        # including this measurement's own workflow, on its first commit.
        with mock.patch.object(sh.subprocess, "run", self._gh(1, stderr="gh: Not Found (HTTP 404)")):
            self.assertEqual(sh.gh_runs("owner/repo", "brand-new.yml"), [])

    def test_any_other_failure_is_still_an_error(self):
        with mock.patch.object(sh.subprocess, "run", self._gh(1, stderr="HTTP 401: Bad credentials")):
            with self.assertRaises(RuntimeError):
                sh.gh_runs("owner/repo", "generate-episode.yml")

    def test_run_timestamps_come_back_as_utc(self):
        body = '{"workflow_runs": [{"created_at": "2026-11-14T09:23:00Z"}]}'
        with mock.patch.object(sh.subprocess, "run", self._gh(0, stdout=body)):
            found = sh.gh_runs("owner/repo", "generate-episode.yml")
        self.assertEqual(found, [datetime(2026, 11, 14, 9, 23, tzinfo=timezone.utc)])


class TimesViewTests(unittest.TestCase):
    """The view that says whether a named sweep actually happened."""

    def test_only_a_once_a_day_cron_gets_a_slot(self):
        self.assertEqual(sh.daily_slot("11 14 * * *"), (14, 11))
        self.assertEqual(sh.daily_slot("17 5 * * *"), (5, 17))
        # Nothing attributable: a poll, a weekly cron, a malformed one.
        self.assertIsNone(sh.daily_slot("13,43 * * * *"))
        self.assertIsNone(sh.daily_slot("8 11 * * 4"))
        self.assertIsNone(sh.daily_slot("* * * *"))

    def _data(self, stamps: list[datetime], crons: list[str]) -> dict:
        return {
            "repo": "owner/repo", "days": 1,
            "from": NOON - DAY, "to": NOON,
            "workflows": [
                {"workflow": "generate-episode.yml", "crons": crons,
                 "stamps": sorted(stamps), "expected": 3, "delivered": len(stamps),
                 "rate": 0.0, "per_day": 0.0, "median_gap": 0.0, "p90_gap": 0.0,
                 "max_gap": 0.0}
            ],
        }

    def test_a_late_run_is_attributed_with_its_lateness(self):
        at = datetime(2026, 11, 15, 14, 49, tzinfo=timezone.utc)  # 14:11 + 38 min
        text = sh.as_times(self._data([at], ["11 14 * * *"]))
        self.assertIn("14:49(+38m)", text)
        self.assertIn("all fired", text)

    def test_a_missed_sweep_is_named(self):
        at = datetime(2026, 11, 15, 5, 30, tzinfo=timezone.utc)
        text = sh.as_times(self._data([at], ["17 5 * * *", "11 14 * * *"]))
        self.assertIn("05:30(+13m)", text)
        self.assertIn("missed: 11 14 * * *", text)

    def test_a_run_too_far_from_any_cron_is_left_unattributed(self):
        # The original mistake was calling a 20:00 run a late 14:00 sweep.
        # It is also what a six-hour window did to a real 10:39 run.
        at = datetime(2026, 11, 15, 20, 0, tzinfo=timezone.utc)
        text = sh.as_times(self._data([at], ["11 14 * * *"]))
        self.assertIn("20:00", text)
        self.assertNotIn("20:00(+", text)
        self.assertIn("missed: 11 14 * * *", text)

    def test_a_poll_cron_gets_times_but_no_attribution(self):
        at = datetime(2026, 11, 15, 13, 20, tzinfo=timezone.utc)
        text = sh.as_times(self._data([at], ["13,43 * * * *"]))
        self.assertIn("13:20", text)
        self.assertNotIn("(+", text)
        self.assertNotIn("missed", text)

    def test_the_window_is_tight_enough_to_refuse_a_wrong_match(self):
        # 10:39 against a 07:28 cron is +191 minutes: not that cron's run.
        at = datetime(2026, 11, 15, 10, 39, tzinfo=timezone.utc)
        text = sh.as_times(self._data([at], ["28 7 * * *"]))
        self.assertNotIn("(+", text)
        self.assertIn("missed: 28 7 * * *", text)

    def test_more_runs_than_ticks_is_called_out(self):
        # The crons come from the working tree, the runs from history, so a
        # window spanning a cron change reads as over-delivery. Real case:
        # pulling the half-hourly poll out of generate-episode made three days
        # of its history read as 211%.
        for workflow in ("generate-episode.yml", "friday-podcast.yml"):
            with self.subTest(workflow=workflow):
                data = sh.report("owner/repo", 1, fetch=lambda r, w: (
                    [datetime.now(tz=timezone.utc) - timedelta(minutes=n) for n in range(9)]
                    if w == workflow else []
                ))
                self.assertIn("the crons changed inside this window", sh.as_text(data))

    def test_no_runs_says_so(self):
        self.assertIn("no scheduled runs", sh.as_times(self._data([], ["11 14 * * *"])))


class RealWorkflowTests(unittest.TestCase):
    def test_the_repos_own_crons_parse(self):
        found = {}
        for path in sorted(sh.WORKFLOWS.glob("*.yml")):
            for cron in sh.crons_in(path):
                found[cron] = sh.expected(cron, NOON - 7 * DAY, NOON)
        self.assertTrue(found, "no crons found in .github/workflows")
        for cron, ticks in found.items():
            with self.subTest(cron=cron):
                self.assertGreater(ticks, 0, f"{cron} would never fire in a week")


if __name__ == "__main__":
    unittest.main()
