"""Workflow schedules: the things YAML will happily let you get wrong.

Nothing here runs a workflow. These are the cheap invariants that have already
cost real time: a cron renamed without the expression that tests for it, two
jobs writing the same files at once, and the mailbox polls' minutes.

Run: uv run python -m unittest discover tests
"""
from __future__ import annotations

import re
import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import schedule_health  # noqa: E402

WORKFLOWS = Path(__file__).resolve().parent.parent / ".github" / "workflows"
CRON_RE = re.compile(r"^\s*-\s*cron:\s*[\'\"](?P<cron>[^\'\"]+)[\'\"]", re.MULTILINE)


def crons(name: str) -> list[str]:
    return CRON_RE.findall((WORKFLOWS / name).read_text(encoding="utf-8"))


def minutes(cron: str) -> list[int]:
    """The minutes a 5-field cron fires on: lists, ranges and steps.

    `int()` over the whole field raised ValueError on a perfectly ordinary
    `5-10`, which reads as a broken test rather than as the schedule it is.
    """
    fires: set[int] = set()
    for part in cron.split()[0].split(","):
        spec, _, step_text = part.partition("/")
        step = int(step_text) if step_text else 1
        if spec == "*":
            low, high = 0, 59
        elif "-" in spec:
            low_text, _, high_text = spec.partition("-")
            low, high = int(low_text), int(high_text)
        else:
            low = high = int(spec)
        fires.update(range(low, high + 1, step))
    return sorted(fires)


def schedule_comparisons(workflow: str) -> list[str]:
    """Cron strings a workflow compares `github.event.schedule` against.

    These decide behaviour — which scheduled run is the publish slot — so each
    one has to name a cron the workflow really declares.
    """
    text = (WORKFLOWS / workflow).read_text(encoding="utf-8")
    return re.findall(r"github\.event\.schedule == \'([^\']+)\'", text)


def sub_daily(cron: str) -> bool:
    """Whether this cron fires more than once a day.

    Counted over a week with schedule_health's cron arithmetic rather than
    guessed from the fields: a hand-rolled version read `0 9-17 * * *` — nine
    times a day — as daily.
    """
    start = datetime(2026, 11, 16, tzinfo=timezone.utc)  # a Monday
    return schedule_health.expected(cron, start, start + timedelta(days=7)) > 7


class MinuteParsingTests(unittest.TestCase):
    """The helper everything below is built on."""

    def test_a_list_of_minutes(self):
        self.assertEqual(minutes("9,24,39,54 * * * *"), [9, 24, 39, 54])

    def test_a_step_and_every_minute(self):
        self.assertEqual(minutes("*/30 * * * *"), [0, 30])
        self.assertEqual(len(minutes("* * * * *")), 60)

    def test_a_range_is_a_schedule_not_an_error(self):
        self.assertEqual(minutes("5-8 * * * *"), [5, 6, 7, 8])
        self.assertEqual(minutes("5-20/5 * * * *"), [5, 10, 15, 20])
        self.assertEqual(minutes("7,10-12 * * * *"), [7, 10, 11, 12])


class CongestedMinuteTests(unittest.TestCase):
    """The mailbox poll stays off :00 and :30 — a preference, not a cure.

    On 2026-11-13 the poll's `*/30` cron ran six times instead of forty-eight
    and somebody who subscribed in the evening heard nothing for hours, so
    every cron in the repository moved off the top and bottom of the hour. The
    data since says that was not the cause: scheduled runs here have been
    delivered four to seven times a day for eighteen days, before and after
    the change. The polls keep the odd minutes anyway, because they are the
    schedules somebody is actually waiting on and it costs nothing — but this
    is no longer asserted over every workflow, where it would only block a
    legitimate cron in the name of a theory that did not hold.
    """

    def test_the_mailbox_poll_does_not_fire_on_the_hour_or_the_half_hour(self):
        for cron in crons("mailing-list.yml"):
            with self.subTest(cron=cron):
                fires = minutes(cron)
                self.assertNotIn(0, fires, "fires on the hour")
                self.assertNotIn(30, fires, "fires on the half hour")


class CrowdingTests(unittest.TestCase):
    """The workflow that owns the publish slot asks for three ticks a day.

    Measured over eighteen days, generate-episode was delivered 102 of the 918
    ticks its crons asked for — about five a day, at times matching none of its
    three sweeps — while a neighbouring workflow's single weekly cron was
    delivered every time. GitHub appears to hand a workflow roughly five
    scheduled runs a day however many it asks for, so a half-hourly cron
    sharing a workflow with the daily sweeps spends the budget the sweeps need.

    This pins the experiment: re-adding a sub-daily cron here would quietly put
    the publish slot and the PDF windows back in the lottery. A poll belongs in
    a workflow of its own, where the thing it starves is only itself.
    """

    def test_the_sub_daily_test_recognises_a_busy_cron(self):
        # The guard below is only as good as this.
        self.assertTrue(sub_daily("13,43 * * * *"))
        self.assertTrue(sub_daily("*/30 * * * *"))
        self.assertTrue(sub_daily("0 9-17 * * *"))
        self.assertTrue(sub_daily("0 */4 * * *"))
        self.assertFalse(sub_daily("11 14 * * *"))
        self.assertFalse(sub_daily("8 11 * * 4"))
        self.assertFalse(sub_daily("23 9 * * 1"))

    def test_generate_episode_has_only_daily_schedules(self):
        for cron in crons("generate-episode.yml"):
            with self.subTest(cron=cron):
                self.assertFalse(
                    sub_daily(cron),
                    f"{cron} fires more than once a day in the workflow that owns "
                    "the publish slot; give it its own workflow",
                )

    def test_the_publish_slot_is_one_of_those_schedules(self):
        self.assertIn("11 14 * * *", crons("generate-episode.yml"))


class ScheduleComparisonTests(unittest.TestCase):
    """A comparison against a cron string must name a cron that exists."""

    def test_every_comparison_names_a_real_cron(self):
        # Rename a cron without its comparison and the behaviour it gates —
        # the publish slot — silently stops happening on schedule.
        checked = 0
        for path in sorted(WORKFLOWS.glob("*.yml")):
            declared = crons(path.name)
            for named in schedule_comparisons(path.name):
                checked += 1
                with self.subTest(workflow=path.name, cron=named):
                    self.assertIn(named, declared)
        self.assertGreater(checked, 0, "no schedule comparisons found at all")

    def test_the_publish_slot_names_one(self):
        self.assertIn("11 14 * * *", schedule_comparisons("generate-episode.yml"))


class MailingListWorkflowTests(unittest.TestCase):
    """Its two jobs write the same two files from two clones.

    On a workflow_dispatch they both ran at once — observed starting a second
    apart — and git stopped the lost update by rejecting the second push,
    which turns clicking "Run workflow" into a failed run and an alert Issue.
    """

    def setUp(self) -> None:
        self.text = (WORKFLOWS / "mailing-list.yml").read_text(encoding="utf-8")

    def test_a_dispatch_queues_behind_a_run_already_going(self):
        self.assertRegex(self.text, r"(?m)^concurrency:\n  group: mailing-list$")
        self.assertIn("cancel-in-progress: false", self.text)

    def test_the_sync_job_waits_for_the_poll(self):
        self.assertIn("\n  sync:\n", self.text)
        self.assertIn("needs: poll", self.text.split("\n  sync:\n", 1)[1])


if __name__ == "__main__":
    unittest.main()
