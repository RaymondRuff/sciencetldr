"""Workflow schedules: the things YAML will happily let you get wrong.

Nothing here runs a workflow. These are the cheap invariants that have already
cost real time: a cron that fires on a congested minute and gets dropped, and
a cron renamed without the expression that tests for it.

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
    """The minutes a 5-field cron fires on, for the shapes used here."""
    field = cron.split()[0]
    if field.startswith("*/"):
        step = int(field[2:])
        return list(range(0, 60, step))
    if field == "*":
        return list(range(60))
    return [int(part) for part in field.split(",")]


class CongestedMinuteTests(unittest.TestCase):
    """GitHub delays scheduled runs most at :00, and drops them under load.

    On 2026-11-13 the mailbox poll's `*/30` cron — which fires at :00 and :30 —
    ran six times instead of forty-eight, so somebody who subscribed in the
    evening heard nothing for hours. Every schedule here now avoids the top
    and bottom of the hour.
    """

    def test_no_schedule_fires_on_the_hour_or_the_half_hour(self):
        for workflow in sorted(WORKFLOWS.glob("*.yml")):
            for cron in crons(workflow.name):
                with self.subTest(workflow=workflow.name, cron=cron):
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


if __name__ == "__main__":
    unittest.main()
