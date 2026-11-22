"""The pickers never trade the week's best paper away without asking.

Run: uv run python -m unittest discover tests
"""
from __future__ import annotations

import sys
import unittest
from unittest import mock
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import paper_text  # noqa: E402
import pdf_window  # noqa: E402
import select_monday_paper as monday  # noqa: E402

TEXT = paper_text.Fetched("full text " * 3000, "europepmc:PMC1")


def paper(title, dice=None):
    return {"title": title, "doi": f"10.1/{title}", "dice": dice}


def fetcher(open_titles=(), down_titles=()):
    tried = []

    def fetch(p):
        tried.append(p["title"])
        if p["title"] in down_titles:
            raise paper_text.TransientFetchError("timeout")
        return (f"https://oa/{p['title']}.pdf", TEXT if p["title"] in open_titles else None)

    return fetch, tried


def monday_plan(candidates, fetch):
    return monday.plan_pick(
        candidates, floor=candidates[0]["dice"] - 1, fetch=fetch, same_standard=monday.same_dice
    )


class PlanTests(unittest.TestCase):
    def test_an_open_top_pick_goes_ahead_without_looking_further(self):
        fetch, tried = fetcher(open_titles={"a"})
        plan = monday_plan([paper("a", 5), paper("b", 5)], fetch)
        self.assertEqual(plan.chosen["title"], "a")
        self.assertIs(plan.fetched, TEXT)
        self.assertFalse(plan.window)
        self.assertEqual(tried, ["a"])

    def test_an_open_paper_of_the_same_score_takes_the_slot_without_asking(self):
        fetch, _ = fetcher(open_titles={"b"})
        plan = monday_plan([paper("a", 5), paper("b", 5)], fetch)
        self.assertEqual(plan.chosen["title"], "b")
        self.assertFalse(plan.window)
        self.assertIn("a: no open full text", plan.notes[0])

    def test_a_lower_scoring_paper_does_not_take_the_slot_it_stands_by(self):
        fetch, _ = fetcher(open_titles={"c"})
        plan = monday_plan([paper("a", 5), paper("b", 5), paper("c", 4)], fetch)
        self.assertEqual(plan.chosen["title"], "a")  # the best paper keeps the slot
        self.assertIsNone(plan.fetched)
        self.assertTrue(plan.window)
        self.assertEqual(plan.runner_up["title"], "c")
        self.assertEqual(plan.runner_up_url, "https://oa/c.pdf")
        self.assertEqual(plan.notes, ["b: no open full text"])

    def test_nothing_below_the_floor_stands_in(self):
        fetch, tried = fetcher(open_titles={"c"})
        plan = monday_plan([paper("a", 5), paper("b", 4), paper("c", 3)], fetch)
        self.assertTrue(plan.window)
        self.assertIsNone(plan.runner_up)  # the slot is skipped rather than settle
        self.assertNotIn("c", tried)

    def test_friday_always_asks_because_rank_is_not_a_score(self):
        fetch, _ = fetcher(open_titles={"2"})
        plan = monday.plan_pick([paper("1"), paper("2")], fetch=fetch)
        self.assertEqual(plan.chosen["title"], "1")
        self.assertTrue(plan.window)
        self.assertEqual(plan.runner_up["title"], "2")

    def test_the_search_for_a_runner_up_is_bounded(self):
        fetch, tried = fetcher(open_titles={"z"})
        candidates = [paper(str(i)) for i in range(20)] + [paper("z")]
        plan = monday.plan_pick(candidates, max_tries=8, fetch=fetch)
        self.assertEqual(len(tried), 8)
        self.assertIsNone(plan.runner_up)

    def test_a_source_that_is_down_is_noted_and_passed(self):
        fetch, _ = fetcher(open_titles={"c"}, down_titles={"b"})
        plan = monday_plan([paper("a", 5), paper("b", 5), paper("c", 5)], fetch)
        self.assertEqual(plan.chosen["title"], "c")
        self.assertTrue(any("source was down" in n for n in plan.notes))


class OutageTests(unittest.TestCase):
    """A source that is down is not a paywall."""

    def test_the_top_pick_gets_two_more_chances(self):
        attempts, slept = [], []

        def flaky(p):
            attempts.append(p["title"])
            if len(attempts) < 3:
                raise paper_text.TransientFetchError("503")
            return ("https://oa/a.pdf", TEXT)

        plan = monday.plan_pick([paper("a", 5)], fetch=flaky, sleep=slept.append)
        self.assertIs(plan.fetched, TEXT)
        self.assertFalse(plan.window)
        self.assertEqual(slept, list(monday.TOP_RETRY_DELAYS))

    def test_candidates_that_could_not_be_checked_are_kept_for_the_deadline(self):
        fetch, _ = fetcher(open_titles={"d"}, down_titles={"a", "b"})
        plan = monday.plan_pick(
            [paper("a", 5), paper("b", 5), paper("c", 5), paper("d", 4)],
            floor=4, fetch=fetch, same_standard=monday.same_dice, sleep=lambda s: None,
        )
        self.assertTrue(plan.window)
        self.assertEqual([p["title"] for p in plan.unchecked], ["b"])
        self.assertEqual(plan.runner_up["title"], "d")
        _, body, _, _ = monday.render_pick(plan, "monday-digest")
        stand_ins = body.split('"stand_ins": ')[1]
        self.assertLess(stand_ins.index('"b"'), stand_ins.index('"d"'))  # higher rank first

    def test_with_everything_down_the_body_does_not_promise_a_skip(self):
        fetch, _ = fetcher(down_titles={"a", "b"})
        plan = monday.plan_pick(
            [paper("a", 5), paper("b", 5)], floor=4, fetch=fetch, sleep=lambda s: None
        )
        _, body, _, _ = monday.render_pick(plan, "monday-digest")
        self.assertIn("whose sources were down are tried again", body)


class BodyTests(unittest.TestCase):
    def test_a_window_says_when_and_what_stands_in(self):
        fetch, _ = fetcher(open_titles={"c"})
        plan = monday_plan([paper("a", 5), paper("c", 4)], fetch)
        picked = pdf_window.parse_iso("2026-11-09T14:30:00Z")
        _, body, deadline, runner = monday.render_pick(plan, "monday-digest", picked_at=picked)
        self.assertIn("waiting for a PDF until 9:00 pm Pacific on Mon 9 Nov (05:00 UTC)", body)
        self.assertIn("**c** (DICE 4) stands in", body)
        self.assertIn('"pdf_deadline": "2026-11-10T05:00:00Z"', body)
        self.assertIn('"pdf_url": "https://oa/c.pdf"', body)
        self.assertEqual(runner["title"], "c")
        self.assertNotIn("inbox/pdfs", body)  # never steer a paywalled PDF into the public repo

    def test_with_no_runner_up_the_body_says_the_slot_is_skipped(self):
        fetch, _ = fetcher()
        plan = monday_plan([paper("a", 5), paper("b", 3)], fetch)
        _, body, _, runner = monday.render_pick(plan, "monday-digest")
        self.assertIsNone(runner)
        self.assertIn("this slot is skipped", body)
        self.assertIn('"runner_up": null', body)

    def test_a_staged_paper_needs_no_window(self):
        fetch, _ = fetcher(open_titles={"a"})
        _, body, deadline, _ = monday.render_pick(monday_plan([paper("a", 5)], fetch), "monday-digest")
        self.assertIsNone(deadline)
        self.assertIn("staged for the writer from `europepmc:PMC1`", body)
        self.assertNotIn("pdf_deadline", body)


if __name__ == "__main__":
    unittest.main()


class AlreadyCoveredTests(unittest.TestCase):
    """The Monday picker will not queue a paper the show has already done.

    The Friday crawl has always checked DOIs against published episodes and
    open Issues; the Monday picker never did, because its candidates come from
    a digest of the week just gone and the overlap looked impossible. It is
    not: a paper emailed in as a one-off on the Tuesday can be the digest's
    top-scoring paper by the Sunday. A closed Issue is not in the pending
    list, so rank_queue cannot catch it downstream either.
    """

    def paper(self, doi: str, dice: int = 4, title: str = "A paper") -> dict:
        return {"doi": doi, "title": title, "dice": dice, "is_preprint": False}

    def covered(self, *dois: str):
        return mock.patch.object(
            monday.select_friday_paper,
            "already_seen_dois",
            lambda: {d.lower() for d in dois},
        )

    def test_a_paper_already_published_is_dropped(self):
        papers = [self.paper("10.1038/done"), self.paper("10.1038/fresh")]
        with self.covered("10.1038/done"):
            kept = monday.drop_covered(papers)
        self.assertEqual([p["doi"] for p in kept], ["10.1038/fresh"])

    def test_the_comparison_ignores_case(self):
        with self.covered("10.1038/DONE"):
            kept = monday.drop_covered([self.paper("10.1038/done")])
        self.assertEqual(kept, [])

    def test_a_paper_with_no_doi_is_left_alone(self):
        # Nothing to compare; the white-paper path has its own URL check.
        with self.covered("10.1038/done"):
            kept = monday.drop_covered([self.paper("")])
        self.assertEqual(len(kept), 1)

    def test_nothing_covered_changes_nothing(self):
        papers = [self.paper("10.1038/a"), self.paper("10.1038/b")]
        with self.covered():
            self.assertEqual(monday.drop_covered(papers), papers)

    def test_a_check_that_cannot_run_keeps_every_candidate(self):
        # A Monday with no episode is worse than a small risk of a repeat.
        def boom():
            raise RuntimeError("github unreachable")

        papers = [self.paper("10.1038/a")]
        with mock.patch.object(
            monday.select_friday_paper, "already_seen_dois", boom
        ):
            self.assertEqual(monday.drop_covered(papers), papers)

    def test_dropping_the_top_paper_lowers_the_floor_with_it(self):
        # The floor is DICE minus one from the best *eligible* paper. If a
        # covered five set it, a three would qualify as "the same standard"
        # and could take the slot off a four.
        papers = [
            self.paper("10.1038/done", dice=5),
            self.paper("10.1038/four", dice=4),
            self.paper("10.1038/three", dice=3),
        ]
        with self.covered("10.1038/done"):
            kept = monday.drop_covered(papers)
        self.assertEqual(kept[0]["dice"], 4)
        self.assertEqual(kept[0]["dice"] - 1, 3, "floor follows the top eligible paper")
