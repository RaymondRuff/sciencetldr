"""Emailing a paper in: what counts as a request, and what comes back.

The email path is the only one that lets a message from outside choose what
the show covers, so the sender rules matter as much as the parsing. See
pdf_mailbox.py and generate_episode.queue_one_offs().

Run: uv run python -m unittest discover tests
"""
from __future__ import annotations

import io
import os
import sys
import tempfile
import unittest
from email.message import EmailMessage
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import add_paper  # noqa: E402
import generate_episode as ge  # noqa: E402
import pdf_mailbox as mailbox  # noqa: E402

DOI = "10.1016/j.chembiol.2026.09.022"
OWNER = "ray@example.com"


class SubjectTests(unittest.TestCase):
    def test_a_request_starts_with_one_off_and_the_rest_is_a_note(self):
        self.assertEqual(mailbox.one_off_note("one-off: the spacer paper"), "the spacer paper")
        self.assertEqual(mailbox.one_off_note("One Off — HERV-K"), "HERV-K")
        self.assertEqual(mailbox.one_off_note("Re: one-off"), "")
        self.assertEqual(mailbox.one_off_note("Fwd: ONE-OFF  please"), "please")

    def test_the_phrase_has_to_lead(self):
        # Otherwise an ordinary sentence commissions an episode.
        self.assertIsNone(mailbox.one_off_note("just a one-off thought about figures"))
        self.assertIsNone(mailbox.one_off_note("fibre paper"))

    def test_a_reply_to_a_numbered_request_is_not_a_one_off(self):
        subject = "Re: [Science TLDR #40] PDF wanted by 9:00 pm Pacific: Whitehall"
        self.assertIsNotNone(mailbox.SUBJECT_RE.search(subject))

    def test_our_own_confirmation_carries_the_tag_so_a_pdf_reply_is_matched(self):
        # queue_one_offs() answers with this shape; the reply pass must own it.
        subject = f"[{mailbox.SUBJECT_TAG}112] one-off: the spacer paper"
        self.assertEqual(int(mailbox.SUBJECT_RE.search(subject).group(1)), 112)


class DoiTests(unittest.TestCase):
    def test_distinct_dois_in_order(self):
        text = f"see https://doi.org/{DOI} and 10.1038/x-1, plus {DOI} again."
        self.assertEqual(mailbox.dois_in(text), [DOI, "10.1038/x-1"])

    def test_trailing_punctuation_is_not_part_of_the_doi(self):
        self.assertEqual(mailbox.dois_in(f"({DOI})."), [DOI])

    def test_nothing_in_nothing(self):
        self.assertEqual(mailbox.dois_in(""), [])
        self.assertEqual(mailbox.dois_in("no identifiers here"), [])

    def test_a_doi_is_read_off_a_real_pdf(self):
        try:
            from reportlab.pdfgen import canvas
        except ImportError:
            self.skipTest("reportlab is not installed")
        buffer = io.BytesIO()
        pdf = canvas.Canvas(buffer)
        pdf.drawString(70, 760, "Shared alpha-helix chimeraffibodies")
        pdf.drawString(70, 740, f"https://doi.org/{DOI}")
        pdf.showPage()
        pdf.save()
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "paper.pdf"
            path.write_bytes(buffer.getvalue())
            self.assertEqual(add_paper.doi_from_pdf(path), DOI)

    def test_an_unreadable_pdf_yields_nothing_rather_than_raising(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "broken.pdf"
            path.write_bytes(b"%PDF-1.4 this is not really a pdf")
            self.assertIsNone(add_paper.doi_from_pdf(path))


class SenderTests(unittest.TestCase):
    def test_only_the_owner_may_commission_an_episode(self):
        env = {"PDF_REQUEST_TO": OWNER, "PDF_SENDER_ALLOWLIST": "colleague@lab.edu"}
        with mock.patch.dict(os.environ, env):
            self.assertEqual(mailbox.owner_address(), OWNER)
            # A colleague may satisfy a PDF request but not choose a paper.
            self.assertIn("colleague@lab.edu", mailbox.allowed_senders())
            self.assertNotEqual(mailbox.owner_address(), "colleague@lab.edu")

    def test_a_display_name_and_a_list_are_tolerated(self):
        with mock.patch.dict(os.environ, {"PDF_REQUEST_TO": f"Ray <{OWNER}>, other@x.com"}):
            self.assertEqual(mailbox.owner_address(), OWNER)

    def test_no_owner_configured_means_no_one_off_path(self):
        with mock.patch.dict(os.environ, {"PDF_REQUEST_TO": ""}):
            self.assertEqual(mailbox.owner_address(), "")
            self.assertEqual(mailbox._collect_one_offs(None, Path(".")), [])

    def test_gmails_verdict_is_what_decides_a_sender_is_real(self):
        msg = EmailMessage()
        msg["From"] = f"Ray <{OWNER}>"
        msg["Authentication-Results"] = "mx.google.com; dmarc=pass header.from=example.com"
        self.assertTrue(mailbox._authenticated(msg, OWNER))
        forged = EmailMessage()
        forged["From"] = f"Ray <{OWNER}>"
        forged["Authentication-Results"] = "mx.google.com; dkim=fail; spf=fail; dmarc=fail"
        self.assertFalse(mailbox._authenticated(forged, OWNER))


class QueueTests(unittest.TestCase):
    """What the sweep does with the requests the mailbox saved."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.drop = Path(self._tmp.name)
        self.calls = []
        self.requests = []
        self.result = add_paper.Queued(112, "A real paper", DOI, True)

        def from_email(request):
            if isinstance(self.result, Exception):
                raise self.result
            return self.result

        patches = [
            mock.patch.object(mailbox, "one_offs_received", lambda: list(self.requests)),
            mock.patch.object(mailbox, "drop_dir", lambda: self.drop),
            mock.patch.object(mailbox, "answer",
                              lambda subject, body: self.calls.append(("answer", subject, body)) or True),
            mock.patch.object(mailbox, "mark_uid",
                              lambda uid, label=mailbox.LABEL_PROCESSED: self.calls.append(("mark", uid)) or True),
            mock.patch.object(mailbox, "record_reply",
                              lambda n, uid, path: self.calls.append(("record", n, uid, Path(path).name))),
            mock.patch.object(add_paper, "from_email", from_email),
        ]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)

    def answer(self) -> tuple[str, str]:
        found = next(c for c in self.calls if c[0] == "answer")
        return found[1], found[2]

    def test_nothing_waiting_does_nothing(self):
        self.assertEqual(ge.queue_one_offs(), [])
        self.assertEqual(self.calls, [])

    def test_a_doi_only_request_is_answered_and_the_email_consumed(self):
        self.requests = [{"uid": "9", "subject": "one-off: spacers", "note": "spacers",
                          "dois": [DOI], "pdf": None}]
        self.assertEqual(ge.queue_one_offs(), [])
        subject, body = self.answer()
        self.assertEqual(subject, f"[{mailbox.SUBJECT_TAG}112] one-off: spacers")
        self.assertIn("Queued as Issue #112", body)
        self.assertIn("08:00 UTC", body)
        self.assertIn(("mark", "9"), self.calls)
        self.assertNotIn("record", [c[0] for c in self.calls])

    def test_an_attached_pdf_is_handed_to_the_reply_path(self):
        attached = self.drop / "one-off-9.pdf"
        attached.write_bytes(b"%PDF-1.7 x")
        self.requests = [{"uid": "9", "subject": "one-off", "note": "",
                          "dois": [DOI], "pdf": str(attached)}]
        ge.queue_one_offs()
        self.assertIn(("record", 112, "9", "issue-112.pdf"), self.calls)
        self.assertTrue((self.drop / "issue-112.pdf").is_file())
        self.assertFalse(attached.exists())
        # consume_replies() consumes it later, once it cannot be lost.
        self.assertNotIn("mark", [c[0] for c in self.calls])

    def test_a_paper_with_no_text_is_asked_for_by_return(self):
        self.result = add_paper.Queued(112, "A real paper", DOI, False)
        self.requests = [{"uid": "9", "subject": "one-off", "note": "", "dois": [DOI], "pdf": None}]
        ge.queue_one_offs()
        _, body = self.answer()
        self.assertIn("Reply to this email with the PDF attached", body)
        self.assertIn("papers/issue-112.pdf", body)

    def test_a_refusal_is_explained_and_not_retried(self):
        self.result = add_paper.Refused("that paper is already published")
        self.requests = [{"uid": "9", "subject": "one-off: dupe", "note": "dupe",
                          "dois": [DOI], "pdf": None}]
        self.assertEqual(ge.queue_one_offs(), [])
        subject, body = self.answer()
        self.assertEqual(subject, "Re: one-off: dupe")
        self.assertIn("already published", body)
        self.assertIn(("mark", "9"), self.calls)

    def test_an_unexpected_failure_keeps_the_email_for_the_next_sweep(self):
        self.result = RuntimeError("gh is down")
        self.requests = [{"uid": "9", "subject": "one-off", "note": "", "dois": [DOI], "pdf": None}]
        problems = ge.queue_one_offs()
        self.assertEqual(len(problems), 1)
        self.assertIn("could not be queued", problems[0])
        self.assertEqual(self.calls, [])  # no answer, no label: it is retried

    def test_each_request_is_answered_once(self):
        self.requests = [
            {"uid": "9", "subject": "one-off: a", "note": "a", "dois": [DOI], "pdf": None},
            {"uid": "10", "subject": "one-off: b", "note": "b", "dois": ["10.1/b"], "pdf": None},
        ]
        ge.queue_one_offs()
        self.assertEqual(len([c for c in self.calls if c[0] == "answer"]), 2)
        self.assertEqual(len([c for c in self.calls if c[0] == "mark"]), 2)


if __name__ == "__main__":
    unittest.main()
