"""Publishing an episode makes no model call unless asked to.

Run: uv run python -m unittest discover tests
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import publish_episode as pe  # noqa: E402

META = {
    "title": "Shared α-helix chimeraffibodies",
    "doi": "10.1016/j.chembiol.2026.09.022",
    "journal": "Cell Chemical Biology",
    "source_url": "https://doi.org/10.1016/j.chembiol.2026.09.022",
}


class ShowNotesTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.audio = Path(self._tmp.name) / "issue-90-x.mp3"
        self.audio.write_bytes(b"ID3")
        patcher = mock.patch.object(
            pe, "generate_show_notes", side_effect=AssertionError("paid call")
        )
        self.paid = patcher.start()
        self.addCleanup(patcher.stop)

    def test_the_routines_notes_are_used_and_consumed(self):
        sidecar = self.audio.with_suffix(".notes.md")
        sidecar.write_text("**[A paper](x)**\n\n**Question:** Q?\n", encoding="utf-8")
        notes = pe.show_notes_for(self.audio, META, transcript="Nadia: hi")
        self.assertIn("**Question:** Q?", notes)
        self.assertFalse(sidecar.exists())
        self.paid.assert_not_called()

    def test_without_notes_the_metadata_speaks_for_itself(self):
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("SHOW_NOTES_VIA_API", None)
            notes = pe.show_notes_for(self.audio, META, transcript=None)
        self.assertIn("**[Shared α-helix chimeraffibodies](https://doi.org/", notes)
        self.assertIn("*Cell Chemical Biology*", notes)
        self.assertIn("DOI: [10.1016/j.chembiol.2026.09.022]", notes)
        self.paid.assert_not_called()

    def test_the_api_runs_only_when_switched_on(self):
        self.paid.side_effect = None
        self.paid.return_value = "notes from Sonnet"
        with mock.patch.dict(os.environ, {"SHOW_NOTES_VIA_API": "true"}):
            notes = pe.show_notes_for(self.audio, META, transcript=None)
        self.assertEqual(notes, "notes from Sonnet")

    def test_a_white_paper_gets_a_source_line(self):
        notes = pe.metadata_show_notes({"title": "A report", "source_url": "https://org.example/r.pdf"})
        self.assertIn("Source: [https://org.example/r.pdf]", notes)


def an_issue(number: int, meta: dict) -> dict:
    body = "<!-- METADATA -->\n```json\n" + json.dumps(meta) + "\n```\n<!-- /METADATA -->"
    return {"number": number, "title": f"Issue {number}", "body": body}


class PairingTests(unittest.TestCase):
    """The audio says which Issue it belongs to, so publishing cannot misfile it."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.audio = Path(self._tmp.name) / "episode.mp3"
        self.audio.write_bytes(b"ID3")
        self.comment = ""
        patches = [
            mock.patch.object(pe, "extract_comment", lambda path: self.comment),
            mock.patch.object(pe, "crossref_metadata", self.crossref),
            mock.patch.object(pe, "pubmed_abstract_for_doi", lambda doi: "An abstract."),
        ]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)

    def crossref(self, doi):
        return {"title": "The canonical title", "doi": doi, "authors": ["A B"],
                "journal": "Cell", "abstract": "", "source": "crossref"}

    def test_the_tag_carries_both_the_issue_and_the_doi(self):
        self.assertEqual(pe.extract_issue("Issue: 112; DOI: 10.1016/j.cell.2026.08.039"), 112)
        self.assertEqual(pe.extract_doi("Issue: 112; DOI: 10.1016/j.cell.2026.08.039"), "10.1016/j.cell.2026.08.039")
        self.assertIsNone(pe.extract_issue("DOI: 10.1016/j.cell.2026.08.039"))

    def test_it_pairs_by_number_not_by_age(self):
        # The old fallback took pending[0], the oldest open Issue.
        pending = [
            an_issue(40, {"title": "Whitehall diet", "doi": "10.1007/s00394-026-03986-w", "source": "friday-reddit"}),
            an_issue(112, {"title": "1. The paper", "doi": "10.1016/j.chembiol.2026.09.022", "source": "monday-digest"}),
        ]
        self.comment = "Issue: 112; DOI: 10.1016/j.chembiol.2026.09.022"
        meta, issue = pe.resolve_metadata(self.audio, pending)
        self.assertEqual(issue["number"], 112)
        self.assertEqual(meta["doi"], "10.1016/j.chembiol.2026.09.022")

    def test_crossref_supplies_the_title_but_the_strand_survives(self):
        pending = [an_issue(112, {"title": "1. The paper", "doi": "10.1016/j.chembiol.2026.09.022",
                                  "source": "monday-digest"})]
        self.comment = "Issue: 112; DOI: 10.1016/j.chembiol.2026.09.022"
        meta, _ = pe.resolve_metadata(self.audio, pending)
        self.assertEqual(meta["title"], "The canonical title")  # not "1. The paper"
        self.assertEqual(meta["source"], "monday-digest")  # not "crossref"
        self.assertEqual(meta["source_url"], "https://doi.org/10.1016/j.chembiol.2026.09.022")
        self.assertEqual(meta["abstract"], "An abstract.")

    def test_a_white_paper_pairs_and_keeps_its_url(self):
        pending = [
            an_issue(40, {"title": "Whitehall diet", "doi": "10.1007/s00394-026-03986-w", "source": "friday-reddit"}),
            an_issue(113, {"title": "A white paper", "doi": None, "source": "one-off",
                           "source_url": "https://example.org/wp.pdf",
                           "journal": "White paper — Example Lab"}),
        ]
        self.comment = "Issue: 113"
        with mock.patch.object(pe, "crossref_metadata",
                               lambda doi: self.fail("a white paper has no DOI to look up")):
            meta, issue = pe.resolve_metadata(self.audio, pending)
        self.assertEqual(issue["number"], 113)
        self.assertEqual(meta["title"], "A white paper")
        self.assertEqual(meta["source_url"], "https://example.org/wp.pdf")
        self.assertEqual(meta["journal"], "White paper — Example Lab")
        self.assertEqual(meta["source"], "one-off")

    def test_a_tag_for_an_issue_that_is_closed_falls_back_to_the_doi(self):
        pending = [an_issue(40, {"title": "Whitehall diet", "doi": "10.1007/s00394-026-03986-w",
                                 "source": "friday-reddit"})]
        self.comment = "Issue: 999; DOI: 10.1007/s00394-026-03986-w"
        meta, issue = pe.resolve_metadata(self.audio, pending)
        # The DOI branch takes over and still finds the right Issue.
        self.assertEqual(issue["number"], 40)
        self.assertEqual(meta["title"], "The canonical title")

    def test_a_white_paper_with_no_tag_at_all_is_not_misfiled_silently(self):
        # Belt and braces: without a tag the old oldest-pending guess remains,
        # so the tag is what every generated episode must carry.
        pending = [an_issue(40, {"title": "Whitehall diet", "doi": "10.1007/s00394-026-03986-w",
                                 "source": "friday-reddit"})]
        self.comment = ""
        _, issue = pe.resolve_metadata(self.audio, pending)
        self.assertEqual(issue["number"], 40)


if __name__ == "__main__":
    unittest.main()
