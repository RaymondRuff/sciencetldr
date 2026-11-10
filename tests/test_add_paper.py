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
import paper_text  # noqa: E402  (Fetched)
import routine_tools  # noqa: E402

TEXT = paper_text.Fetched("full text " * 3000, "europepmc-pdf:PMC7", b"%PDF")
DOI = "10.1016/j.chembiol.2026.09.022"


class AddTests(unittest.TestCase):
    def setUp(self):
        self.calls = []
        self.fetched = TEXT
        self.seen = set()
        self.emailed = True
        self.outstanding = []

        def obtain(paper):
            if isinstance(self.fetched, Exception):
                raise self.fetched
            return ("https://oa/x.pdf" if self.fetched else None), self.fetched

        patches = [
            mock.patch.object(add_paper.github_issue, "ensure_auth", lambda: None),
            mock.patch.object(add_paper.github_issue, "open_issues_with_label",
                              lambda label: list(self.outstanding)),
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
        queued = add_paper.add(DOI, note="the spacer claim")
        self.assertEqual((queued.number, queued.staged, queued.doi), (42, True, DOI))
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
        with self.assertRaises(add_paper.Refused):
            add_paper.add("the one about chimeraffibodies")
        self.assertEqual(self.calls, [])

    def test_a_paper_already_published_or_queued_is_refused(self):
        self.seen = {DOI.lower()}
        with self.assertRaises(add_paper.Refused):
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
            with self.assertRaises(add_paper.Refused):
                add_paper.add(DOI)

    def test_a_title_override_wins(self):
        add_paper.add(DOI, title="The title I want")
        self.assertEqual(self.metadata()["title"], "The title I want")


class CapTests(unittest.TestCase):
    """An easy way in must not be an easy way to spend the week's capacity."""

    def setUp(self):
        self.outstanding = []
        patches = [
            mock.patch.object(add_paper.github_issue, "ensure_auth", lambda: None),
            mock.patch.object(add_paper.github_issue, "open_issues_with_label",
                              lambda label: list(self.outstanding)),
            mock.patch.object(add_paper.crossref_lookup, "crossref_metadata",
                              lambda doi: {"title": "A paper"}),
            mock.patch.object(add_paper.crossref_lookup, "pmid_for_doi", lambda doi: ""),
            mock.patch.object(add_paper.select_friday_paper, "already_seen_dois", lambda: set()),
            mock.patch.object(add_paper.select_monday_paper, "obtain", lambda p: (None, TEXT)),
            mock.patch.object(add_paper.select_monday_paper, "stage_for_writer",
                              lambda *a, **k: None),
            mock.patch.object(add_paper.github_issue, "open_issue", lambda **kw: 42),
        ]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)

    def test_four_waiting_is_allowed_to_become_four(self):
        self.outstanding = [101, 102, 103]
        self.assertEqual(add_paper.add(DOI).number, 42)

    def test_a_fifth_is_refused_and_says_which_are_waiting(self):
        self.outstanding = [101, 102, 103, 104]
        with self.assertRaises(add_paper.Refused) as caught:
            add_paper.add(DOI)
        message = str(caught.exception)
        self.assertIn("#101", message)
        self.assertIn("limit of 4", message)

    def test_force_gets_past_the_cap(self):
        self.outstanding = [101, 102, 103, 104, 105]
        self.assertEqual(add_paper.add(DOI, force=True).number, 42)

    def test_a_count_that_fails_does_not_block_the_queue(self):
        def broken(label):
            raise RuntimeError("gh is down")

        with mock.patch.object(add_paper.github_issue, "open_issues_with_label", broken):
            self.assertEqual(add_paper.add(DOI).number, 42)


class FromEmailTests(unittest.TestCase):
    """What an emailed request has to say before it becomes an episode."""

    def setUp(self):
        self.added = []
        patch = mock.patch.object(
            add_paper, "add",
            lambda doi="", **kw: self.added.append((doi, kw))
            or add_paper.Queued(7, "T", doi or kw.get("url", ""), True),
        )
        patch.start()
        self.addCleanup(patch.stop)

    def test_one_doi_in_the_body_is_used(self):
        add_paper.from_email({"dois": [DOI], "note": "why", "pdf": None})
        doi, kw = self.added[0]
        self.assertEqual(doi, DOI)
        self.assertEqual(kw["note"], "why")
        self.assertIsNone(kw["pdf"])
        self.assertFalse(kw["email_request"])  # the confirmation covers it

    def test_several_dois_are_refused_rather_than_guessed(self):
        with self.assertRaises(add_paper.Refused) as caught:
            add_paper.from_email({"dois": [DOI, "10.1/other"], "pdf": None})
        self.assertIn("several DOIs", str(caught.exception))
        self.assertEqual(self.added, [])

    def test_no_doi_and_no_pdf_asks_for_the_doi(self):
        with self.assertRaises(add_paper.Refused) as caught:
            add_paper.from_email({"dois": [], "pdf": None})
        self.assertIn("could not find a DOI", str(caught.exception))

    def test_a_pdf_is_read_for_its_doi(self):
        with mock.patch.object(add_paper, "doi_from_pdf", lambda path: DOI):
            add_paper.from_email({"dois": [], "pdf": "/tmp/x.pdf", "note": ""})
        doi, kw = self.added[0]
        self.assertEqual(doi, DOI)
        self.assertEqual(kw["pdf"], Path("/tmp/x.pdf"))

    def test_a_single_link_identifies_a_paper_with_no_doi(self):
        add_paper.from_email({
            "dois": [], "urls": ["https://example.org/wp.pdf"], "pdf": None,
            "fields": {"title": "A white paper", "publisher": "Example Lab"},
            "note": "worth a look",
        })
        doi, kw = self.added[0]
        self.assertEqual(doi, "")
        self.assertEqual(kw["url"], "https://example.org/wp.pdf")
        self.assertEqual(kw["title"], "A white paper")
        self.assertEqual(kw["publisher"], "Example Lab")

    def test_an_explicit_url_line_beats_a_forest_of_links(self):
        add_paper.from_email({
            "dois": [], "pdf": None,
            "urls": ["https://news.example/x", "https://unsubscribe.example/y"],
            "fields": {"url": "https://example.org/wp.pdf"},
        })
        self.assertEqual(self.added[0][1]["url"], "https://example.org/wp.pdf")

    def test_several_links_and_no_url_line_is_refused(self):
        with self.assertRaises(add_paper.Refused) as caught:
            add_paper.from_email({
                "dois": [], "pdf": None,
                "urls": ["https://a.example/x", "https://b.example/y"],
            })
        self.assertIn("'URL:'", str(caught.exception))

    def test_a_doi_still_wins_over_a_link(self):
        add_paper.from_email({"dois": [DOI], "urls": ["https://example.org/wp.pdf"], "pdf": None})
        self.assertEqual(self.added[0][0], DOI)
        self.assertNotIn("url", self.added[0][1])

    def test_organisation_is_spelled_either_way(self):
        for key in ("publisher", "organisation", "organization", "org"):
            self.added.clear()
            add_paper.from_email({
                "dois": [], "pdf": None, "urls": ["https://example.org/wp.pdf"],
                "fields": {"title": "A white paper", key: "Example Lab"},
            })
            self.assertEqual(self.added[0][1]["publisher"], "Example Lab", key)

    def test_a_pdf_with_no_readable_doi_is_refused(self):
        with mock.patch.object(add_paper, "doi_from_pdf", lambda path: None):
            with self.assertRaises(add_paper.Refused) as caught:
                add_paper.from_email({"dois": [], "pdf": "/tmp/x.pdf"})
        self.assertIn("attached PDF", str(caught.exception))

    def test_a_doi_in_the_body_beats_the_pdf(self):
        with mock.patch.object(add_paper, "doi_from_pdf", lambda path: "10.1/from-pdf"):
            add_paper.from_email({"dois": [DOI], "pdf": "/tmp/x.pdf"})
        self.assertEqual(self.added[0][0], DOI)


class WhitePaperTests(unittest.TestCase):
    """A paper with no DOI is identified by where it was published."""

    def setUp(self):
        self.calls = []
        self.fetched = paper_text.Fetched("text " * 4000, "pdf-url", b"%PDF-1.7")
        patches = [
            mock.patch.object(add_paper.github_issue, "ensure_auth", lambda: None),
            mock.patch.object(add_paper.github_issue, "open_issues_with_label", lambda l: []),
            mock.patch.object(add_paper.select_friday_paper, "already_seen_urls", lambda: set()),
            mock.patch.object(add_paper.select_monday_paper, "obtain",
                              lambda p: (p.get("pdf_url"), self.fetched)),
            mock.patch.object(add_paper.select_monday_paper, "stage_for_writer",
                              lambda n, p, f, journal="": self.calls.append(("stage", journal))),
            mock.patch.object(add_paper.github_issue, "open_issue",
                              lambda **kw: self.calls.append(("open", kw)) or 55),
            mock.patch.object(add_paper.crossref_lookup, "crossref_metadata",
                              lambda doi: self.fail("a white paper has no Crossref record")),
        ]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)

    def body(self) -> str:
        return next(c[1]["body"] for c in self.calls if c[0] == "open")

    def metadata(self) -> dict:
        return json.loads(self.body().split("```json")[1].split("```")[0])

    def test_it_is_queued_with_its_url_and_no_doi(self):
        queued = add_paper.add(
            url="https://example.org/wp.pdf", title="A white paper", publisher="Example Lab"
        )
        self.assertEqual((queued.number, queued.doi, queued.staged),
                         (55, "https://example.org/wp.pdf", True))
        meta = self.metadata()
        self.assertIsNone(meta["doi"])
        self.assertEqual(meta["source_url"], "https://example.org/wp.pdf")
        self.assertEqual(meta["journal"], "White paper — Example Lab")
        self.assertIn("**Paper:** [https://example.org/wp.pdf]", self.body())
        self.assertIn("No DOI: this is a white paper", meta["digest_excerpt"])

    def test_the_title_is_read_off_the_pdf_when_it_is_not_given(self):
        with mock.patch.object(add_paper, "title_from_pdf", lambda data: "Read off the page"):
            queued = add_paper.add(url="https://example.org/wp.pdf")
        self.assertEqual(queued.title, "Read off the page")
        self.assertEqual(self.metadata()["title"], "Read off the page")

    def test_an_untitled_unreadable_paper_is_refused_rather_than_guessed(self):
        with mock.patch.object(add_paper, "title_from_pdf", lambda data: None):
            with self.assertRaises(add_paper.Refused) as caught:
                add_paper.add(url="https://example.org/wp.pdf")
        self.assertIn("Send the title", str(caught.exception))
        self.assertEqual(self.calls, [])

    def test_a_link_that_is_not_a_link_is_refused(self):
        with self.assertRaises(add_paper.Refused):
            add_paper.add(url="rfd4-proteina.org/paper.pdf")

    def test_neither_a_doi_nor_a_url_is_refused(self):
        with self.assertRaises(add_paper.Refused) as caught:
            add_paper.add()
        self.assertIn("either a DOI or a link", str(caught.exception))

    def test_a_url_already_queued_is_refused(self):
        with mock.patch.object(add_paper.select_friday_paper, "already_seen_urls",
                               lambda: {"https://example.org/wp.pdf"}):
            with self.assertRaises(add_paper.Refused):
                add_paper.add(url="https://example.org/wp.pdf", title="A white paper")

    def test_a_url_that_serves_no_pdf_asks_for_one(self):
        self.fetched = None
        with mock.patch.object(add_paper.pdf_mailbox, "request", lambda n, **kw: True), \
             mock.patch.object(add_paper.github_issue, "add_labels",
                               lambda n, labels: self.calls.append(("label", labels))):
            queued = add_paper.add(url="https://example.org/page.html", title="A white paper")
        self.assertFalse(queued.staged)
        self.assertIn(("label", ["needs-pdf", "pdf-requested"]), self.calls)


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
