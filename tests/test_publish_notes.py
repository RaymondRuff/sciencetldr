"""Publishing an episode makes no model call unless asked to.

Run: uv run python -m unittest discover tests
"""
from __future__ import annotations

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


if __name__ == "__main__":
    unittest.main()
