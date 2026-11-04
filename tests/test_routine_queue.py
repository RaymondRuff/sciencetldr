"""The writer chooses its Issue mechanically, and never reports a thing twice.

Run: uv run python -m unittest discover tests
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import routine_tools  # noqa: E402

NOTES = """**[A paper](https://doi.org/10.1/x)**

*Journal, 2026*

DOI: [10.1/x](https://doi.org/10.1/x)

**Question:** Does it work?

**Answer:** In 40 mice, partly.

**Three takeaways**

1. It worked in 40 mice.
2. No human data.
3. One lab.
"""


def issue(number, *labels, created="2026-10-01T00:00:00Z", pr=False):
    found = {
        "number": number,
        "created_at": created,
        "labels": [{"name": n} for n in ("podcast-pending", *labels)],
    }
    if pr:
        found["pull_request"] = {}
    return found


class QueueTests(unittest.TestCase):
    def rank(self, issues, *, scripts=(), branches=(), bundled=()):
        return routine_tools.rank_queue(
            issues,
            scripts_on_main=set(scripts),
            branches=list(branches),
            bundled=set(bundled),
        )

    def test_the_six_stalled_issues_are_skipped_without_a_word(self):
        # The morning of 2026-11-04: every Issue was waiting on a PDF that had
        # already been asked for, and the writer pushed a notification for each.
        stalled = [issue(n, "needs-pdf", "pdf-requested") for n in (40, 43, 44, 48, 58, 85)]
        order, skipped = self.rank(stalled)
        self.assertEqual(order, [])
        self.assertEqual({n for n, _ in skipped}, {40, 43, 44, 48, 58, 85})
        self.assertTrue(all("already asked" in reason for _, reason in skipped))

    def test_a_staged_paper_goes_first_even_if_it_was_waiting_on_a_pdf(self):
        issues = [
            issue(41, created="2026-09-01T00:00:00Z"),
            issue(90, "needs-pdf", created="2026-11-02T00:00:00Z"),
        ]
        order, _ = self.rank(issues, bundled={90})
        self.assertEqual(order, [90, 41])

    def test_oldest_first_within_each_group(self):
        issues = [
            issue(92, created="2026-11-03T00:00:00Z"),
            issue(91, created="2026-11-02T00:00:00Z"),
            issue(94, created="2026-11-05T00:00:00Z"),
            issue(93, created="2026-11-04T00:00:00Z"),
        ]
        order, _ = self.rank(issues, bundled={93, 94})
        self.assertEqual(order, [93, 94, 91, 92])

    def test_work_already_in_hand_is_skipped(self):
        issues = [
            issue(1, "episode-in-review"),
            issue(2, "generation-failed"),
            issue(3),
            issue(4),
            issue(5, pr=True),
        ]
        order, skipped = self.rank(
            issues, scripts={3}, branches=["claude/routine-issue-4"], bundled={1, 2, 3, 4}
        )
        self.assertEqual(order, [])
        reasons = dict(skipped)
        self.assertIn("waiting to publish", reasons[1])
        self.assertIn("needs Ray", reasons[2])
        self.assertIn("on main", reasons[3])
        self.assertIn("claude/routine-issue-4", reasons[4])
        self.assertNotIn(5, reasons)  # a pull request is not an Issue

    def test_issue_numbers_sharing_a_prefix_are_not_confused(self):
        self.assertTrue(routine_tools.mentions_issue("episode/issue-90-chimeras", 90))
        self.assertTrue(routine_tools.mentions_issue("claude/routine-issue-9", 9))
        self.assertFalse(routine_tools.mentions_issue("claude/routine-issue-90", 9))
        self.assertFalse(routine_tools.mentions_issue("claude/routine-issue-9", 90))
        self.assertFalse(routine_tools.mentions_issue("episode/issue-190-x", 90))


class ParkTests(unittest.TestCase):
    def test_park_labels_and_comments_over_rest(self):
        calls = []
        with mock.patch.object(routine_tools, "_gh_api", lambda path, *a: calls.append((path, a)) or "{}"):
            code = routine_tools.cmd_park(43, "needs-pdf", Path("/tmp/note.md"))
        self.assertEqual(code, 0)
        self.assertEqual(calls[0][0], "repos/RaymondRuff/sciencetldr/issues/43/labels")
        self.assertIn("labels[]=needs-pdf", calls[0][1])
        self.assertEqual(calls[1][0], "repos/RaymondRuff/sciencetldr/issues/43/comments")
        self.assertIn("body=@/tmp/note.md", calls[1][1])

    def test_a_failed_label_is_reported_not_hidden(self):
        with mock.patch.object(routine_tools, "_gh_api", lambda *a: None):
            self.assertEqual(routine_tools.cmd_park(43, "needs-pdf", None), 1)

    def test_no_prompt_or_tool_reaches_for_graphql(self):
        # `gh issue list --json` and `gh pr list --json` are GraphQL, which the
        # routine sandbox refuses. Everything a routine runs must be REST.
        root = Path(__file__).resolve().parent.parent
        for path in [*root.glob("prompts/routine_*.md"), root / "scripts" / "routine_tools.py"]:
            text = path.read_text(encoding="utf-8")
            for banned in ("gh issue list", "gh pr list", "gh issue view", "gh pr view", "gh api graphql"):
                self.assertNotIn(banned, text, f"{path.name} uses {banned}")


class ShowNotesTests(unittest.TestCase):
    def test_well_formed_notes_pass(self):
        self.assertEqual(routine_tools.validate_show_notes(NOTES), [])

    def test_notes_are_required(self):
        self.assertTrue(routine_tools.validate_show_notes(None))
        self.assertTrue(routine_tools.validate_show_notes("   "))

    def test_each_part_is_required(self):
        errors = routine_tools.validate_show_notes(NOTES.replace("**Answer:**", "Answer:"))
        self.assertTrue(any("Answer" in e for e in errors), errors)

    def test_three_takeaways_exactly(self):
        errors = routine_tools.validate_show_notes(NOTES + "4. And another.\n")
        self.assertTrue(any("three numbered" in e for e in errors), errors)

    def test_the_word_budget_holds(self):
        long = NOTES.replace("Does it work?", "Does it work? " + "and then more " * 60)
        errors = routine_tools.validate_show_notes(long)
        self.assertTrue(any("words" in e for e in errors), errors)

    def test_no_hype(self):
        errors = routine_tools.validate_show_notes(NOTES.replace("partly", "a breakthrough"))
        self.assertTrue(any("hype" in e for e in errors), errors)


if __name__ == "__main__":
    unittest.main()
