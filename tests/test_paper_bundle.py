"""Tests for scripts/paper_bundle.py.  Run: uv run python -m unittest discover tests"""
from __future__ import annotations

import io
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import paper_bundle as pb  # noqa: E402
import paper_text  # noqa: E402


class CaptionTests(unittest.TestCase):
    def test_caption_at_line_start_is_found(self):
        page = (
            "...and the effect persisted in both cohorts.\n"
            "Fig 1. Associations between exposure and outcome in the whole "
            "cohort, with hazard ratios and confidence intervals.\n"
            "https://doi.org/10.1371/journal.pmed.1005251.g001\n"
        )
        found = pb.find_captions([page])
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0]["label"], "Fig 1")
        self.assertEqual(found[0]["kind"], "figure")
        self.assertEqual(found[0]["page"], 1)
        self.assertIn("hazard ratios", found[0]["caption"])
        # The publisher's per-figure DOI stamp closes the caption and belongs
        # to it; nothing after it leaks in.
        self.assertTrue(found[0]["caption"].endswith(".g001"))

    def test_inline_cross_reference_is_not_a_caption(self):
        page = "The association weakened after adjustment (Fig 1) in every model."
        self.assertEqual(pb.find_captions([page]), [])

    def test_bare_label_without_prose_is_skipped(self):
        self.assertEqual(pb.find_captions(["Fig 2. Study flow\n"]), [])

    def test_a_heading_ends_a_caption(self):
        page = (
            "Table 4. Sensitivity analyses across every specification tested "
            "in the study.\n"
            "Discussion\n"
            "We found little evidence of an association.\n"
        )
        found = pb.find_captions([page])
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0]["kind"], "table")
        self.assertNotIn("little evidence", found[0]["caption"])

    def test_next_caption_ends_the_previous_one(self):
        page = (
            "Fig 1. First figure, showing the primary outcome over follow-up.\n"
            "Fig 2. Second figure, showing the same outcome by subgroup.\n"
        )
        found = pb.find_captions([page])
        self.assertEqual([c["label"] for c in found], ["Fig 1", "Fig 2"])
        self.assertNotIn("Second figure", found[0]["caption"])

    def test_a_table_gets_more_room_than_a_figure(self):
        filler = "row of numbers 1.00 0.95 0.88 " * 400  # ~11k chars
        figure = pb.find_captions([f"Fig 1. A caption {filler}"])[0]
        table = pb.find_captions([f"Table 1. A caption {filler}"])[0]
        self.assertLess(len(figure["caption"]), len(table["caption"]))
        self.assertTrue(figure["caption"].endswith("[...truncated]"))
        self.assertGreater(len(table["caption"]), pb.MAX_CAPTION_CHARS)


class FigureTests(unittest.TestCase):
    def test_small_and_elongated_images_are_decorative(self):
        self.assertTrue(pb._is_decorative(233, 233))  # a journal logo
        self.assertTrue(pb._is_decorative(38, 50))  # an ORCID icon
        self.assertTrue(pb._is_decorative(2000, 40))  # a rule
        self.assertFalse(pb._is_decorative(1762, 1128))  # a real forest plot
        self.assertFalse(pb._is_decorative(1937, 948))

    def test_encode_downsamples_and_picks_a_format(self):
        from PIL import Image

        image = Image.new("RGB", (3000, 1500), "white")
        data, ext = pb._encode(image, 1600)
        self.assertIn(ext, ("png", "jpg"))
        self.assertEqual(max(Image.open(io.BytesIO(data)).size), 1600)

    def test_figures_are_paired_with_captions_on_their_own_page(self):
        figures = [
            {"file": "figures/fig-p09-01.png", "page": 9},
            {"file": "figures/fig-p11-01.png", "page": 11},
        ]
        captions = [
            {"label": "Fig 1", "kind": "figure", "page": 9, "caption": "first"},
            {"label": "Fig 2", "kind": "figure", "page": 11, "caption": "second"},
            {"label": "Table 1", "kind": "table", "page": 9, "caption": "a table"},
        ]
        pb.pair_figures(figures, captions)
        self.assertEqual(figures[0]["label"], "Fig 1")
        self.assertEqual(figures[1]["label"], "Fig 2")
        self.assertEqual(captions[0]["image"], "figures/fig-p09-01.png")
        # A table never claims an image, even on a page that has one.
        self.assertNotIn("image", captions[2])

    def test_an_image_with_no_caption_keeps_its_place(self):
        figures = [{"file": "figures/fig-p03-01.png", "page": 3}]
        pb.pair_figures(figures, [])
        self.assertEqual(figures[0]["label"], "")
        section = pb.figures_section([], figures)
        self.assertIn("unlabelled image", section)
        self.assertIn("figures/fig-p03-01.png", section)


class AwkwardPdfTests(unittest.TestCase):
    """Publishers ship PDFs that are out of spec. Losing the paper is not an option."""

    @staticmethod
    def _page_with_font_files(*keys):
        from pypdf.generic import DictionaryObject, NameObject, NumberObject

        descriptor = DictionaryObject()
        for index, key in enumerate(keys):
            descriptor[NameObject(key)] = NumberObject(index)
        font = DictionaryObject()
        font[NameObject("/FontDescriptor")] = descriptor
        fonts = DictionaryObject()
        fonts[NameObject("/F1")] = font
        resources = DictionaryObject()
        resources[NameObject("/Font")] = fonts
        page = DictionaryObject()
        page[NameObject("/Resources")] = resources
        return page, descriptor

    def test_a_second_font_program_is_dropped(self):
        # Cell Chemical Biology embeds HelveticaNeue with both, and pypdf
        # raises rather than reading the page.
        page, descriptor = self._page_with_font_files("/FontFile", "/FontFile3")
        reader = type("R", (), {"pages": [page]})()
        self.assertEqual(pb._drop_duplicate_font_files(reader), 1)
        self.assertIn("/FontFile", descriptor)
        self.assertNotIn("/FontFile3", descriptor)

    def test_a_well_formed_font_is_left_alone(self):
        page, descriptor = self._page_with_font_files("/FontFile2")
        reader = type("R", (), {"pages": [page]})()
        self.assertEqual(pb._drop_duplicate_font_files(reader), 0)
        self.assertIn("/FontFile2", descriptor)

    def test_a_page_without_fonts_is_not_an_error(self):
        from pypdf.generic import DictionaryObject

        reader = type("R", (), {"pages": [DictionaryObject()]})()
        self.assertEqual(pb._drop_duplicate_font_files(reader), 0)


class TrimTests(unittest.TestCase):
    """The collected captions must survive `prepare_paper_text`."""

    def test_figures_section_survives_a_references_heading(self):
        body = "Introduction\n" + ("body text. " * 2000)
        text = (
            body
            + "\nReferences\n"
            + ("1. Author A. A paper. Journal. 2020.\n" * 50)
        )
        prepared = paper_text.prepare_paper_text(text)
        self.assertNotIn("Author A", prepared)

        bundled = prepared + pb.figures_section(
            [{"label": "Fig 1", "kind": "figure", "page": 9, "caption": "Fig 1. x"}],
            [],
        )
        # Preparing an already-prepared bundle is a no-op, not the loss of
        # its most valuable section.
        self.assertEqual(paper_text.prepare_paper_text(bundled), bundled)
        self.assertIn("FIGURES AND TABLES", paper_text.prepare_paper_text(bundled))

    def test_marker_matches_what_the_section_writes(self):
        section = pb.figures_section([], [])
        self.assertIn(paper_text.FIGURES_MARKER, section)


class BundleTests(unittest.TestCase):
    """End to end over a generated PDF, so no fixture is committed."""

    @classmethod
    def setUpClass(cls):
        from PIL import Image, ImageDraw

        try:
            from reportlab.pdfgen import canvas  # noqa: F401
        except ImportError:
            cls.pdf = None
            return
        from reportlab.lib.utils import ImageReader
        from reportlab.pdfgen import canvas

        plot = Image.new("RGB", (1800, 1000), "white")
        draw = ImageDraw.Draw(plot)
        for x in range(0, 1800, 37):
            draw.line([(x, 0), (x, 1000)], fill=(20, 60, 140), width=3)

        buffer = io.BytesIO()
        pdf = canvas.Canvas(buffer)
        pdf.drawString(70, 760, "Introduction")
        pdf.drawString(70, 740, "We studied the thing in a large cohort. " * 3)
        pdf.showPage()
        pdf.drawImage(ImageReader(plot), 50, 400, width=500, height=278)
        pdf.drawString(50, 380, "Fig 1. Hazard ratios for the primary outcome,")
        pdf.drawString(50, 365, "estimated with a Cox model across five quintiles.")
        pdf.showPage()
        pdf.save()
        cls.pdf = buffer.getvalue()

    def setUp(self):
        if self.pdf is None:
            self.skipTest("reportlab not installed")

    def test_build_writes_text_figures_and_meta(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "issue-1"
            meta = pb.build(self.pdf, 1, out, doi="10.1234/test", title="A paper")

            self.assertEqual(meta["issue"], 1)
            self.assertEqual(meta["doi"], "10.1234/test")
            self.assertEqual(meta["pages"], 2)
            self.assertEqual(len(meta["pdf_sha256"]), 64)

            text = (out / "paper.txt").read_text(encoding="utf-8")
            self.assertIn("large cohort", text)
            self.assertIn("FIGURES AND TABLES", text)
            self.assertIn("Fig 1", text)

            self.assertEqual(
                json.loads((out / "meta.json").read_text(encoding="utf-8"))["issue"], 1
            )
            for figure in meta["figures"]:
                self.assertTrue((out / figure["file"]).is_file())
                self.assertEqual((out / figure["file"]).stat().st_size, figure["bytes"])

    def test_build_is_reproducible_over_the_same_pdf(self):
        with tempfile.TemporaryDirectory() as tmp:
            a = pb.build(self.pdf, 1, Path(tmp) / "a")
            b = pb.build(self.pdf, 1, Path(tmp) / "b")
            self.assertEqual(a["pdf_sha256"], b["pdf_sha256"])
            self.assertEqual(a["text_chars"], b["text_chars"])
            self.assertEqual(len(a["figures"]), len(b["figures"]))

    def test_bundle_is_far_smaller_than_the_pdf_it_came_from(self):
        with tempfile.TemporaryDirectory() as tmp:
            meta = pb.build(self.pdf, 1, Path(tmp) / "issue-1")
            self.assertLess(meta["bundle_bytes"], pb.BUNDLE_BUDGET)


class CacheTests(unittest.TestCase):
    def test_cached_returns_none_without_a_bundle(self):
        with tempfile.TemporaryDirectory() as tmp:
            import os

            os.environ["PAPER_BUNDLE_DIR"] = tmp
            try:
                self.assertIsNone(pb.cached(7))
                bundle = Path(tmp) / "issue-7"
                bundle.mkdir()
                (bundle / "paper.txt").write_text("x" * 100, encoding="utf-8")
                self.assertEqual(pb.cached(7), bundle)
            finally:
                os.environ.pop("PAPER_BUNDLE_DIR", None)

    def test_paper_text_reads_a_cached_bundle(self):
        with tempfile.TemporaryDirectory() as tmp:
            import os

            os.environ["PAPER_BUNDLE_DIR"] = tmp
            try:
                bundle = Path(tmp) / "issue-7"
                bundle.mkdir()
                (bundle / "paper.txt").write_text(
                    "a" * (paper_text.MIN_USEFUL_CHARS + 1), encoding="utf-8"
                )
                result = paper_text.from_bundle(7)
                self.assertIsNotNone(result)
                self.assertEqual(result[1], "bundle:issue-7")
                # Too short to be a paper: treated as no bundle at all.
                (bundle / "paper.txt").write_text("short", encoding="utf-8")
                self.assertIsNone(paper_text.from_bundle(7))
            finally:
                os.environ.pop("PAPER_BUNDLE_DIR", None)

    def test_sync_all_does_nothing_without_work(self):
        self.assertEqual(pb.sync_all([]), {})


class FindRawPdfTests(unittest.TestCase):
    """Matching an upload to its Issue by whatever name it arrived under."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.repo = pb.PapersRepo.__new__(pb.PapersRepo)
        self.repo.dir = Path(self.tmp.name)
        (self.repo.dir / "papers").mkdir()

    def drop(self, name: str) -> Path:
        path = self.repo.papers / name
        path.write_bytes(b"%PDF-1.4 ")
        return path

    def test_issue_number_filename_wins(self):
        self.drop("issue-90.pdf")
        self.drop("something-else.pdf")
        found = self.repo.find_raw_pdf(90, "10.1016/j.chembiol.2026.09.022")
        self.assertEqual(found.name, "issue-90.pdf")

    def test_doi_suffix_in_filename_matches(self):
        self.drop("journal.pmed.1005251.pdf")
        found = self.repo.find_raw_pdf(86, "10.1371/journal.pmed.1005251")
        self.assertEqual(found.name, "journal.pmed.1005251.pdf")

    def test_a_publisher_filename_matches_nothing(self):
        # Elsevier names downloads like this: no Issue number, no DOI. The
        # sole-upload claim in sync_all is what covers it.
        self.drop("1-s2.0-S2451945626003234-main.pdf")
        self.assertIsNone(
            self.repo.find_raw_pdf(90, "10.1016/j.chembiol.2026.09.022")
        )

    def test_no_papers_directory_is_not_an_error(self):
        empty = pb.PapersRepo.__new__(pb.PapersRepo)
        empty.dir = Path(self.tmp.name) / "nothing"
        self.assertIsNone(empty.find_raw_pdf(1, "10.1/x"))


if __name__ == "__main__":
    unittest.main()
