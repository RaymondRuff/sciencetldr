"""The pickers choose papers that can be read.

Run: uv run python -m unittest discover tests
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import paper_text  # noqa: E402
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


class ChooseTests(unittest.TestCase):
    def test_an_open_top_pick_is_taken_without_looking_further(self):
        fetch, tried = fetcher(open_titles={"a"})
        chosen, url, fetched, notes = monday.choose_obtainable(
            [paper("a", 5), paper("b", 5)], floor=4, fetch=fetch
        )
        self.assertEqual(chosen["title"], "a")
        self.assertIs(fetched, TEXT)
        self.assertEqual(tried, ["a"])
        self.assertEqual(notes, [])

    def test_a_paywalled_top_pick_gives_way_to_the_next_good_one(self):
        fetch, _ = fetcher(open_titles={"c"})
        chosen, _, fetched, notes = monday.choose_obtainable(
            [paper("a", 5), paper("b", 5), paper("c", 4)], floor=4, fetch=fetch
        )
        self.assertEqual(chosen["title"], "c")
        self.assertIsNotNone(fetched)
        self.assertEqual(len(notes), 2)

    def test_it_never_reaches_below_the_floor(self):
        fetch, tried = fetcher(open_titles={"c"})
        chosen, _, fetched, notes = monday.choose_obtainable(
            [paper("a", 5), paper("b", 4), paper("c", 3)], floor=4, fetch=fetch
        )
        self.assertEqual(chosen["title"], "a")  # the top pick stands, text or not
        self.assertIsNone(fetched)
        self.assertNotIn("c", tried)
        self.assertEqual(len(notes), 1)  # b; the top pick is not "passed over"

    def test_a_source_that_is_down_is_not_counted_as_paywalled(self):
        fetch, _ = fetcher(open_titles={"b"}, down_titles={"a"})
        chosen, _, _, notes = monday.choose_obtainable(
            [paper("a", 5), paper("b", 5)], floor=4, fetch=fetch
        )
        self.assertEqual(chosen["title"], "b")
        self.assertIn("a source was down", notes[0])

    def test_friday_candidates_have_no_floor_but_a_try_limit(self):
        fetch, tried = fetcher(open_titles={"z"})
        candidates = [paper(str(i)) for i in range(20)] + [paper("z")]
        chosen, _, fetched, _ = monday.choose_obtainable(candidates, max_tries=8, fetch=fetch)
        self.assertEqual(len(tried), 8)
        self.assertEqual(chosen["title"], "0")
        self.assertIsNone(fetched)

    def test_the_issue_body_says_what_happened(self):
        body = monday.availability_section(None, ["b: no open full text"])
        self.assertIn("No open full text found", body)
        self.assertIn("Also tried", body)
        self.assertNotIn("inbox/pdfs", body)  # never steer a paywalled PDF into the public repo
        staged = monday.availability_section(TEXT, ["a: no open full text"])
        self.assertIn("staged for the writer from `europepmc:PMC1`", staged)
        self.assertIn("Passed over", staged)


if __name__ == "__main__":
    unittest.main()
