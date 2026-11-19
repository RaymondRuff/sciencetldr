"""The doorbell must never be stricter than the pipeline it rings for.

tools/gmail-doorbell/Code.gs runs in Apps Script on the podcast's Gmail
account and asks generate-episode to run when mail arrives. It parses nothing
and decides nothing — scripts/pdf_mailbox.py owns all of that. But if its
patterns drift narrower than the Python ones, a message the pipeline *would*
act on stops waking it, and the only symptom is a paper quietly taking two
days instead of two minutes.

So: every subject the pipeline acts on must also ring the doorbell. The
reverse is fine and expected — a false ring costs one workflow run that finds
nothing. Writing this test is what caught the first drift: the doorbell
anchored "unsubscribe" to the start of the subject while pdf_mailbox honours
it anywhere, deliberately.

Run: uv run python -m unittest discover tests
"""
from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import pdf_mailbox as mailbox  # noqa: E402

DOORBELL = ROOT / "tools" / "gmail-doorbell" / "Code.gs"
WORKFLOW = ROOT / ".github" / "workflows" / "generate-episode.yml"

# Subjects pdf_mailbox acts on, so the doorbell has to wake for all of them.
ACTED_ON = [
    "One-off",
    "one-off: the spacer paper",
    "Re: one-off",
    "Fwd: ONE-OFF  please",
    "One Off — HERV-K",
    "subscribe",
    "Subscribe please",
    "subscribe alice@example.com",
    "subscribe alice@example.com, bob@example.org",
    "unsubscribe carol@example.net",
    "Re: subscribe",
    "unsubscribe",
    "Please UNSUBSCRIBE me",
    "Re: Science TLDR Weekly Digest — unsubscribe",
    "Re: [Science TLDR #40] PDF wanted by 9:00 pm Pacific: Whitehall",
    "[Science TLDR #138] one-off: Seasonal variations",
]

IGNORED = [
    "Your receipt from the conference",
    "how do I subscribe to this?",
    "loved the episode",
]


def javascript_patterns() -> list[re.Pattern]:
    """The /.../i literals Code.gs tests subjects against, as Python regexes.

    The two dialects agree on everything used here: (?:...), \\b, \\s, and the
    i flag. A pattern that stopped translating would fail loudly below rather
    than silently matching nothing.
    """
    source = DOORBELL.read_text(encoding="utf-8")
    found = re.findall(r"^const (?:WANTED|LEAVING|NUMBERED_REPLY) = /(.+)/i;$",
                       source, re.MULTILINE)
    return [re.compile(p.replace("\\/", "/"), re.IGNORECASE) for p in found]


class DoorbellContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.patterns = javascript_patterns()
        self.assertEqual(len(self.patterns), 3, "expected three subject patterns in Code.gs")

    def rings(self, subject: str) -> bool:
        return any(p.search(subject) for p in self.patterns)

    def pipeline_acts_on(self, subject: str) -> bool:
        return (
            mailbox.one_off_note(subject) is not None
            or mailbox.list_request(subject) is not None
            or mailbox.SUBJECT_RE.search(subject) is not None
        )

    def test_the_fixtures_really_are_things_the_pipeline_acts_on(self):
        for subject in ACTED_ON:
            with self.subTest(subject=subject):
                self.assertTrue(self.pipeline_acts_on(subject))

    def test_everything_the_pipeline_acts_on_rings_the_doorbell(self):
        for subject in ACTED_ON:
            with self.subTest(subject=subject):
                self.assertTrue(self.rings(subject), "the pipeline would act; the doorbell sleeps")

    def test_ordinary_mail_does_not_ring_it(self):
        # Not a correctness requirement — a false ring costs one empty run —
        # but a doorbell that rings at everything is a doorbell nobody fixes.
        for subject in IGNORED:
            with self.subTest(subject=subject):
                self.assertFalse(self.rings(subject))
                self.assertFalse(self.pipeline_acts_on(subject))

    def test_unsubscribe_is_honoured_anywhere_on_both_sides(self):
        # The drift this test was written to catch.
        subject = "Re: Science TLDR Weekly Digest — unsubscribe"
        self.assertEqual(mailbox.list_request(subject), "unsubscribe")
        self.assertTrue(self.rings(subject))


class DoorbellWiringTests(unittest.TestCase):
    def setUp(self) -> None:
        self.workflow = WORKFLOW.read_text(encoding="utf-8")

    def test_the_workflow_listens_for_the_doorbell(self):
        self.assertIn("repository_dispatch:", self.workflow)
        self.assertIn("types: [mailbox]", self.workflow)
        self.assertIn("'mailbox'", DOORBELL.read_text(encoding="utf-8"))

    def test_a_doorbell_run_never_takes_the_publish_slot(self):
        slot = next(l for l in self.workflow.splitlines() if "PUBLISH_SLOT:" in l)
        self.assertNotIn("repository_dispatch", slot)
        self.assertNotIn("github.event_name == 'workflow_dispatch'", slot)

    def test_publishing_by_hand_is_opt_in(self):
        self.assertIn("inputs.publish", self.workflow)
        self.assertRegex(self.workflow, r"publish:\n\s+description:.*\n\s+required: false\n")

    def test_the_token_is_never_in_the_script(self):
        source = DOORBELL.read_text(encoding="utf-8")
        self.assertIn("PropertiesService.getScriptProperties()", source)
        self.assertNotRegex(source, r"gh[pous]_[A-Za-z0-9]{16,}")


if __name__ == "__main__":
    unittest.main()
