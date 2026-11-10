"""Queueing one paper by hand opens the same Issue the strands open.

Run: uv run python -m unittest discover tests
"""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import add_paper  # noqa: E402
import paper_text  # noqa: E402
import routine_tools  # noqa: E402

TEXT = paper_text.Fetched("full text " * 3000, "europepmc-pdf:PMC7", b"%PDF")
DOI = "10.1016/j.chembiol.2026.09.022"


class AddTests(unittest.TestCase):
    def setUp(self):
        self.calls = []
        self.fetched = TEXT
        self.seen = set()
        self.emailed = True

        def obtain(paper):
            if isinstance(self.fetched, Exception):
                raise self.fetched
            return ("https://oa/x.pdf" if self.fetched else None), self.fetched

        patches = [
            mock.patch.object(add_paper.github_issue, "ensure_auth", lambda: None),
            mock.patch.object(add_paper.crossref_lookup, "crossref_metadata",
                              lambda doi: {"title": "A real paper", "journal": "Cell"}),
            mock.patch.object(add_paper.crossref_lookup, "pmid_for_doi", lambda doi: "123"),
            mock.patch.object(add_paper.select_friday_paper, "already_seen_dois", lambda: self.seen),
            mock.patch.object(add_paper.select_monday_paper, "obtain", obtain),
            mock.patch.object(add_paper.github_issue, "open_issue",
                              lambda **kw: self.calls.append(("open", kw)) or 42),
            mock.patch.object(add_paper.github_issue, "add_labels",
                              lambda n, labels: self.calls.append(("label", n, labels))),
            mock.patch.object(add_paper.select_monday_paper, "stage_for_writer",
                              lambda n, p, f, journal="": self.calls.append(("stage", n, f.provenance))),
            mock.patch.object(add_paper.pdf_mailbox, "request",
                              lambda n, **kw: self.calls.append(("email", n, kw)) or self.emailed),
        ]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)

    def opened(self) -> dict:
        return next(c[1] for c in self.calls if c[0] == "open")

    def kinds(self) -> list[str]:
        return [c[0] for c in self.calls]

    def metadata(self) -> dict:
        body = self.opened()["body"]
        return json.loads(body.split("```json")[1].split("```")[0])

    def test_an_open_paper_is_staged_and_nobody_is_emailed(self):
        number = add_paper.add(DOI, note="the spacer claim")
        self.assertEqual(number, 42)
        self.assertEqual(self.opened()["labels"], ["podcast-pending", "one-off"])
        self.assertTrue(self.opened()["title"].startswith("🎧 A real paper"))
        self.assertIn(("stage", 42, "europepmc-pdf:PMC7"), self.calls)
        self.assertNotIn("email", self.kinds())

    def test_the_metadata_block_marks_it_a_one_off(self):
        add_paper.add(DOI, note="the spacer claim")
        meta = self.metadata()
        self.assertEqual(meta["source"], "one-off")
        self.assertEqual(meta["doi"], DOI)
        self.assertIsNone(meta["dice_score"])
        self.assertIn("Queued by hand", meta["digest_excerpt"])
        self.assertIn("the spacer claim", meta["digest_excerpt"])

    def test_a_paywalled_paper_is_asked_for_once(self):
        self.fetched = None
        add_paper.add(DOI)
        self.assertNotIn("stage", self.kinds())
        email = next(c for c in self.calls if c[0] == "email")
        self.assertEqual(email[2]["doi"], DOI)
        self.assertNotIn("deadline", email[2])  # no window: a one-off has no runner-up
        self.assertIn(("label", 42, ["needs-pdf", "pdf-requested"]), self.calls)

    def test_an_email_that_cannot_be_sent_still_leaves_needs_pdf(self):
        self.fetched = None
        self.emailed = False
        add_paper.add(DOI)
        self.assertIn(("label", 42, ["needs-pdf"]), self.calls)

    def test_a_source_that_is_down_does_not_crash_the_queueing(self):
        self.fetched = paper_text.TransientFetchError("timeout")
        add_paper.add(DOI)
        self.assertIn("open", self.kinds())
        self.assertIn("email", self.kinds())

    def test_a_doi_pasted_as_a_url_or_with_a_prefix_still_works(self):
        for given in (f"https://doi.org/{DOI}", f"doi:{DOI}", f"  {DOI}  "):
            self.calls.clear()
            add_paper.add(given)
            self.assertEqual(self.metadata()["doi"], DOI)

    def test_something_that_is_not_a_doi_is_refused(self):
        with self.assertRaises(SystemExit):
            add_paper.add("the one about chimeraffibodies")
        self.assertEqual(self.calls, [])

    def test_a_paper_already_published_or_queued_is_refused(self):
        self.seen = {DOI.lower()}
        with self.assertRaises(SystemExit):
            add_paper.add(DOI)
        self.assertEqual(self.calls, [])

    def test_force_overrides_the_duplicate_check(self):
        self.seen = {DOI.lower()}
        add_paper.add(DOI, force=True)
        self.assertIn("open", self.kinds())

    def test_a_preprint_is_flagged_in_the_excerpt(self):
        with mock.patch.object(add_paper.crossref_lookup, "crossref_metadata",
                               lambda doi: {"title": "A preprint", "is_preprint": True}):
            add_paper.add(DOI)
        self.assertIn("not been peer reviewed", self.metadata()["digest_excerpt"])

    def test_no_title_anywhere_is_refused(self):
        with mock.patch.object(add_paper.crossref_lookup, "crossref_metadata", lambda doi: {}):
            with self.assertRaises(SystemExit):
                add_paper.add(DOI)

    def test_a_title_override_wins(self):
        add_paper.add(DOI, title="The title I want")
        self.assertEqual(self.metadata()["title"], "The title I want")


class StrandTests(unittest.TestCase):
    """The writer is told which strand it is writing for."""

    def test_each_strand_names_its_day(self):
        self.assertIn("Monday", routine_tools.describe_strand("monday-digest"))
        self.assertIn("digest", routine_tools.describe_strand("monday-digest"))
        self.assertIn("Friday", routine_tools.describe_strand("friday-reddit"))
        self.assertIn("r/science", routine_tools.describe_strand("friday-reddit"))
        self.assertIn("Friday", routine_tools.describe_strand("friday-trending"))
        self.assertIn("PubMed", routine_tools.describe_strand("friday-trending"))

    def test_a_one_off_is_told_to_claim_no_slot(self):
        for source in ("one-off", "", None, "something-new"):
            self.assertIn("no strand framing" if source != "one-off" else "no strand",
                          routine_tools.describe_strand(source), source)

    def test_the_prompt_documents_every_strand_the_code_emits(self):
        rules = (Path(__file__).resolve().parent.parent / "prompts" / "host_dialogue.md").read_text()
        for source in ("monday-digest", "friday-reddit", "friday-trending"):
            self.assertIn(source, rules, f"{source} is not in the host prompt")


if __name__ == "__main__":
    unittest.main()
