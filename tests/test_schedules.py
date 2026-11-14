"""Workflow schedules: the things YAML will happily let you get wrong.

Nothing here runs a workflow. These are the cheap invariants that have already
cost real time: a cron renamed without the expression that tests for it, two
jobs writing the same files at once, and the mailbox polls' minutes.

Run: uv run python -m unittest discover tests
"""
from __future__ import annotations

import re
import unittest
from pathlib import Path

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


def poll_cron(workflow: str) -> str | None:
    """The cron a workflow compares against to tell a mailbox poll from a sweep."""
    text = (WORKFLOWS / workflow).read_text(encoding="utf-8")
    named = re.search(r"POLL: \$\{\{ github\.event\.schedule == \'([^\']+)\'", text)
    return named.group(1) if named else None


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
    """The two mailbox polls stay off :00 and :30 — a preference, not a cure.

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

    def polls(self) -> list[tuple[str, str]]:
        found = [(name, cron) for name in ("mailing-list.yml",) for cron in crons(name)]
        episode = poll_cron("generate-episode.yml")
        self.assertIsNotNone(episode, "no POLL comparison found")
        found.append(("generate-episode.yml", episode))
        return found

    def test_neither_mailbox_poll_fires_on_the_hour_or_the_half_hour(self):
        for workflow, cron in self.polls():
            with self.subTest(workflow=workflow, cron=cron):
                fires = minutes(cron)
                self.assertNotIn(0, fires, "fires on the hour")
                self.assertNotIn(30, fires, "fires on the half hour")


class PollGateTests(unittest.TestCase):
    """generate-episode tells a poll from a sweep by comparing cron strings."""

    def test_the_poll_gate_names_a_cron_the_workflow_actually_has(self):
        # If these drift apart, POLL is false on every scheduled run and each
        # mailbox poll becomes a full sweep.
        text = (WORKFLOWS / "generate-episode.yml").read_text(encoding="utf-8")
        named = re.search(r"github\.event\.schedule == \'([^\']+)\'\s*\}\}", text)
        self.assertIsNotNone(named, "no POLL comparison found")
        self.assertIn(named.group(1), crons("generate-episode.yml"))

    def test_the_publish_slot_names_one_too(self):
        text = (WORKFLOWS / "generate-episode.yml").read_text(encoding="utf-8")
        slots = re.findall(r"github\.event\.schedule == \'([^\']+)\'", text)
        self.assertTrue(slots)
        for slot in slots:
            with self.subTest(cron=slot):
                self.assertIn(slot, crons("generate-episode.yml"))


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
