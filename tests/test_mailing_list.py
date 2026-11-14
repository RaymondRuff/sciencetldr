"""The digest's mailing list: who is on it, and how they get on and off it.

The list used to be the DIGEST_RECIPIENTS secret, which cannot be read back,
so adding one person meant retyping everyone. These tests pin the two things
that made it safe to move: the people already on the secret keep receiving the
digest with no action from anyone, and leaving sticks whichever source an
address came from.

See scripts/mailing_list.py and the third pass in scripts/pdf_mailbox.py.

Run: uv run python -m unittest discover tests
"""
from __future__ import annotations

import contextlib
import email
import email.policy
import io
import sys
import tempfile
import unittest
from contextlib import contextmanager
from email.message import EmailMessage
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import email_digest  # noqa: E402
import mailing_list as ml  # noqa: E402
import pdf_mailbox as mailbox  # noqa: E402
import send_email  # noqa: E402

LEGACY = "ray@example.com,anna@example.org, ben@example.net"


class FakeIMAP:
    """Just enough IMAP to see what a declined command does.

    imaplib *returns* a "NO" response for a command the server refuses — it
    raises only on "BAD" — so code that does not read the status cannot tell a
    stored label from a refused one.
    """

    def __init__(self, status: str = "OK") -> None:
        self.status = status
        self.commands: list[tuple] = []

    def login(self, *args):
        return "OK", [b""]

    def select(self, *args):
        return "OK", [b""]

    def list(self):
        return "OK", [br'(\HasNoChildren \All) "/" "[Gmail]/All Mail"']

    def uid(self, command, *args):
        self.commands.append((command, *args))
        return self.status, [b""]

    def logout(self):
        return "OK", [b""]


class FakeMailbox(FakeIMAP):
    """A mailbox holding exactly one message, for the collecting pass."""

    def __init__(self, raw: bytes, uid: bytes = b"7") -> None:
        super().__init__("OK")
        self.raw = raw
        self.uid_value = uid

    def uid(self, command, *args):
        self.commands.append((command, *args))
        if command == "SEARCH":
            return "OK", [self.uid_value]
        if command == "FETCH":
            return "OK", [(b"1 (BODY[HEADER] {0})", self.raw)]
        return self.status, [b""]


class FakeRepo:
    """Stands in for a clone of the private papers repository."""

    def __init__(  # noqa: D107 - see the class docstring
        self, directory, *, fails: bool = False, stores: bool = True
    ) -> None:
        self.dir = directory
        self.fails = fails
        self.stores = stores
        self.commits = []

    def commit(self, message: str, paths: tuple[str, ...] = ("papers",)) -> bool:
        if self.fails:
            raise RuntimeError("push rejected")
        self.commits.append((message, paths))
        return self.stores


@contextmanager
def _as_repo(repo):
    yield repo


def _patch_repo(repo):
    return mock.patch.object(ml, "_repo", lambda: _as_repo(repo))


class RosterTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.addCleanup(self.tmp.cleanup)
        self.env = mock.patch.dict("os.environ", {"DIGEST_RECIPIENTS": LEGACY})
        self.env.start()
        self.addCleanup(self.env.stop)

    def roster(self) -> ml.Roster:
        return ml.Roster(FakeRepo(self.dir))

    def test_the_secret_alone_is_a_full_list(self):
        # The migration guarantee: before anything is written, everyone who was
        # on the secret is still a recipient.
        self.assertEqual(
            self.roster().active(),
            ["anna@example.org", "ben@example.net", "ray@example.com"],
        )

    def test_a_new_subscriber_joins_the_people_on_the_secret(self):
        roster = self.roster()
        self.assertEqual(roster.subscribe("New@Example.com"), "added")
        self.assertIn("new@example.com", roster.active())
        self.assertIn("ray@example.com", roster.active())

    def test_someone_from_the_secret_can_still_leave(self):
        # They were never in a file, so suppression is the only way out.
        roster = self.roster()
        self.assertEqual(roster.unsubscribe("anna@example.org"), "removed")
        self.assertNotIn("anna@example.org", roster.active())

    def test_unsubscribing_beats_both_sources(self):
        roster = self.roster()
        roster.subscribe("anna@example.org")
        roster.unsubscribe("anna@example.org")
        roster.save("a change")
        again = self.roster()
        self.assertNotIn("anna@example.org", again.active())

    def test_rejoining_after_leaving_works(self):
        roster = self.roster()
        roster.unsubscribe("new@example.com")
        roster.save("left")
        again = self.roster()
        self.assertEqual(again.subscribe("new@example.com"), "added")
        self.assertIn("new@example.com", again.active())

    def test_subscribing_twice_says_so_and_changes_nothing(self):
        roster = self.roster()
        roster.subscribe("new@example.com")
        self.assertEqual(roster.subscribe("new@example.com"), "already")
        self.assertEqual(roster.subscribe("ray@example.com"), "already")

    def test_an_unknown_address_leaving_is_recorded_anyway(self):
        roster = self.roster()
        self.assertEqual(roster.unsubscribe("stranger@example.com"), "not-on-it")
        self.assertIn("stranger@example.com", roster.unsubscribed)

    def test_a_malformed_address_is_refused(self):
        roster = self.roster()
        self.assertEqual(roster.subscribe("not an address"), "invalid")
        self.assertEqual(roster.unsubscribe("@example.com"), "invalid")

    def test_saving_writes_both_files_and_commits_only_the_list(self):
        repo = FakeRepo(self.dir)
        roster = ml.Roster(repo)
        roster.subscribe("new@example.com")
        roster.unsubscribe("gone@example.com")
        self.assertTrue(roster.save("a change"))
        self.assertEqual(repo.commits[0][1], ("list",))
        text = (self.dir / "list" / "subscribers.txt").read_text()
        self.assertIn("new@example.com", text)
        self.assertIn("gone@example.com", (self.dir / "list" / "unsubscribed.txt").read_text())
        # Comments survive a round trip without becoming addresses.
        self.assertEqual(ml.Roster(repo).subscribers, {"new@example.com"})

    def test_folding_in_the_secret_is_idempotent(self):
        roster = self.roster()
        moved = roster.fold_in_legacy()
        self.assertEqual(len(moved), 3)
        roster.save("folded")
        self.assertEqual(self.roster().fold_in_legacy(), set())

    def test_folding_in_does_not_resurrect_someone_who_left(self):
        roster = self.roster()
        roster.unsubscribe("ben@example.net")
        roster.save("left")
        again = self.roster()
        self.assertNotIn("ben@example.net", again.fold_in_legacy())
        self.assertNotIn("ben@example.net", again.active())


class RecipientsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.addCleanup(self.tmp.cleanup)
        self.env = mock.patch.dict("os.environ", {"DIGEST_RECIPIENTS": LEGACY})
        self.env.start()
        self.addCleanup(self.env.stop)

    def test_recipients_folds_the_secret_into_the_file(self):
        repo = FakeRepo(self.dir)
        with _patch_repo(repo):
            found = ml.recipients()
        self.assertEqual(len(found), 3)
        self.assertIn("ray@example.com", (self.dir / "list" / "subscribers.txt").read_text())
        self.assertEqual(len(repo.commits), 1)

    def test_a_failed_write_still_subtracts_the_unsubscribed(self):
        # The read and the write used to share one `try`, whose `except`
        # answered with the bare secret — which has no suppression list in it.
        # So a rejected push, which is what two writers at once look like,
        # mailed the one person who had asked to be left alone.
        (self.dir / "list").mkdir()
        (self.dir / "list" / "unsubscribed.txt").write_text("ben@example.net\n")
        out = io.StringIO()
        with _patch_repo(FakeRepo(self.dir, fails=True)), contextlib.redirect_stdout(out):
            found = ml.recipients()
        self.assertEqual(found, ["anna@example.org", "ray@example.com"])
        self.assertIn("could not be written", out.getvalue())

    def test_an_unreadable_list_stops_the_send_whatever_the_secret_holds(self):
        # Who has unsubscribed is only knowable from the papers repository, so
        # a clone that fails means we do not know. Exiting non-zero makes
        # alert-on-failure open an Issue: a digest a day late beats one sent to
        # someone who opted out.
        def boom():
            raise RuntimeError("clone failed")

        for secret in (LEGACY, ""):
            with self.subTest(secret="full" if secret else "empty"):
                with mock.patch.dict("os.environ", {"DIGEST_RECIPIENTS": secret}):
                    with mock.patch.object(ml, "_repo", boom):
                        with self.assertRaises(SystemExit) as caught:
                            ml.recipients()
                self.assertIn("could not read", str(caught.exception))


class ApplyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.addCleanup(self.tmp.cleanup)
        self.env = mock.patch.dict("os.environ", {"DIGEST_RECIPIENTS": LEGACY})
        self.env.start()
        self.addCleanup(self.env.stop)

    def test_a_subscribe_and_an_unsubscribe_are_both_answered(self):
        repo = FakeRepo(self.dir)
        with _patch_repo(repo):
            answers = ml.apply_requests(
                [
                    {"uid": "1", "address": "new@example.com", "wants": "subscribe"},
                    {"uid": "2", "address": "ben@example.net", "wants": "unsubscribe"},
                ]
            )
        self.assertEqual([a["outcome"] for a in answers], ["added", "removed"])
        self.assertEqual([a["uid"] for a in answers], ["1", "2"])
        for answer in answers:
            self.assertTrue(answer["subject"])
            # Every reply says how to reverse what just happened.
            self.assertIn("as the subject", answer["body"])
        with _patch_repo(FakeRepo(self.dir)):
            self.assertNotIn("ben@example.net", ml.recipients())

    def test_nothing_is_promised_if_the_change_cannot_be_stored(self):
        # Returning no answers leaves the mail unlabelled, so the next poll
        # tries again rather than replying "you're on the list" untruthfully.
        with _patch_repo(FakeRepo(self.dir, fails=True)):
            self.assertEqual(
                ml.apply_requests(
                    [{"uid": "1", "address": "new@example.com", "wants": "subscribe"}]
                ),
                [],
            )

    def test_a_change_that_stored_nothing_promises_nothing(self):
        # save() answers False when commit() found nothing staged. That was
        # read as success, so the mail was labelled and the reply sent for a
        # change that is not on file anywhere.
        with _patch_repo(FakeRepo(self.dir, stores=False)):
            self.assertEqual(
                ml.apply_requests(
                    [{"uid": "1", "address": "new@example.com", "wants": "subscribe"}]
                ),
                [],
            )

    def test_an_unusable_address_gets_no_reply(self):
        with _patch_repo(FakeRepo(self.dir)):
            self.assertEqual(
                ml.apply_requests([{"uid": "1", "address": "nonsense", "wants": "subscribe"}]),
                [],
            )

    def test_the_footer_names_the_address_to_write_to(self):
        text, html = ml.footer("pod@example.com")
        self.assertIn("pod@example.com", text)
        self.assertIn("unsubscribe", text.lower())
        self.assertIn("mailto:pod@example.com?subject=unsubscribe", html)


class SubjectTests(unittest.TestCase):
    def test_subscribe_has_to_lead_the_subject(self):
        self.assertEqual(mailbox.list_request("subscribe"), "subscribe")
        self.assertEqual(mailbox.list_request("Subscribe please"), "subscribe")
        self.assertEqual(mailbox.list_request("Re: subscribe"), "subscribe")
        # Otherwise a passing mention signs someone up.
        self.assertIsNone(mailbox.list_request("how do I subscribe to this?"))
        self.assertIsNone(mailbox.list_request("loved the episode"))

    def test_unsubscribe_counts_anywhere_in_the_subject(self):
        # Someone leaving is likely to hit reply and type it after our subject,
        # and ignoring that is the one failure worth avoiding.
        self.assertEqual(mailbox.list_request("unsubscribe"), "unsubscribe")
        self.assertEqual(
            mailbox.list_request("Re: Science TLDR Weekly Digest — unsubscribe"),
            "unsubscribe",
        )
        self.assertEqual(mailbox.list_request("Please UNSUBSCRIBE me"), "unsubscribe")

    def test_unsubscribe_is_never_read_as_subscribe(self):
        for subject in ("unsubscribe", "Re: unsubscribe", "Unsubscribe me"):
            self.assertEqual(mailbox.list_request(subject), "unsubscribe")

    def test_the_other_two_passes_keep_their_mail(self):
        self.assertIsNone(mailbox.list_request("[Science TLDR #40] PDF needed: Whitehall"))
        self.assertIsNone(mailbox.list_request("one-off: the spacer paper"))

    def test_automated_mail_is_recognised(self):
        for header, value in (
            ("Auto-Submitted", "auto-replied"),
            ("Precedence", "bulk"),
            ("List-Id", "<something.example.com>"),
        ):
            msg = EmailMessage()
            msg["Subject"] = "unsubscribe"
            msg[header] = value
            self.assertTrue(mailbox.automated(msg), header)

    def test_an_ordinary_message_is_not_automated(self):
        msg = EmailMessage()
        msg["Subject"] = "unsubscribe"
        msg["Auto-Submitted"] = "no"
        self.assertFalse(mailbox.automated(msg))


class LegacySecretTests(unittest.TestCase):
    """Reading the DIGEST_RECIPIENTS secret, which nobody can read back.

    Dropping one of its entries would silently unsubscribe a real person, so
    these cover the forms it might plausibly have been typed in.
    """

    def _parsed(self, raw: str):
        with mock.patch.dict("os.environ", {"DIGEST_RECIPIENTS": raw}):
            return ml.legacy_parts()

    def test_plain_comma_separated(self):
        self.assertEqual(self._parsed("a@x.com,b@y.org"), ({"a@x.com", "b@y.org"}, 0))

    def test_a_display_name_is_still_an_address(self):
        # smtplib strips the name on the way out, so the old code delivered to
        # this; refusing it now would quietly drop someone.
        self.assertEqual(
            self._parsed("Ray Ruff <ray@x.com>, anna@y.org"),
            ({"ray@x.com", "anna@y.org"}, 0),
        )

    def test_semicolons_separate_too(self):
        self.assertEqual(self._parsed("ray@x.com; anna@y.org"), ({"ray@x.com", "anna@y.org"}, 0))

    def test_a_trailing_comma_does_not_wipe_the_list(self):
        # email.utils.getaddresses() answers this whole string with [("", "")]
        # on Python 3.13, which would have discarded every subscriber. Hence
        # one entry at a time.
        self.assertEqual(self._parsed("a@x.com, b@y.org,"), ({"a@x.com", "b@y.org"}, 0))

    def test_case_and_padding_do_not_make_a_second_person(self):
        self.assertEqual(self._parsed("  Ray@X.com , ray@x.com "), ({"ray@x.com"}, 0))

    def test_an_unreadable_entry_is_counted_not_ignored(self):
        kept, unreadable = self._parsed("a@x.com, oops, b@y.org")
        self.assertEqual(kept, {"a@x.com", "b@y.org"})
        self.assertEqual(unreadable, 1)

    def test_an_empty_secret_is_not_an_error(self):
        self.assertEqual(self._parsed(""), (set(), 0))

    def test_entries_are_counted_separately_from_addresses(self):
        # Six entries yielding five addresses means two are the same person,
        # which is a different problem from one having gone missing.
        with mock.patch.dict("os.environ", {"DIGEST_RECIPIENTS": "a@x.com, A@x.com, b@y.org"}):
            kept, unreadable, entries = ml.legacy_counted()
        self.assertEqual((sorted(kept), unreadable, entries), (["a@x.com", "b@y.org"], 0, 3))


class SyncTests(unittest.TestCase):
    """`mailing_list.py sync` makes the roster readable without a send."""

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.addCleanup(self.tmp.cleanup)

    def _sync(self, raw: str = LEGACY) -> tuple[int, str]:
        repo = FakeRepo(self.dir)
        out = io.StringIO()
        with mock.patch.dict("os.environ", {"DIGEST_RECIPIENTS": raw}, clear=False):
            with _patch_repo(repo), contextlib.redirect_stdout(out):
                count = ml.sync()
        self.repo = repo
        return count, out.getvalue()

    def test_it_writes_the_file_and_reports_the_count(self):
        count, log = self._sync()
        self.assertEqual(count, 3)
        self.assertIn("3 will receive the next digest", log)
        self.assertEqual(self.repo.commits[0][1], ("list",))
        stored = (self.dir / "list" / "subscribers.txt").read_text()
        for address in ("ray@example.com", "anna@example.org", "ben@example.net"):
            self.assertIn(address, stored)

    def test_no_address_is_ever_printed(self):
        # This runs in a public repository's Actions logs.
        _, log = self._sync()
        self.assertNotIn("@", log)

    def test_a_repeated_address_is_explained(self):
        _, log = self._sync("ray@example.com, Ray@example.com, anna@example.org")
        self.assertIn("2 distinct address(es)", log)
        self.assertIn("repeat an address already counted", log)

    def test_an_unreadable_entry_is_called_out(self):
        _, log = self._sync("ray@example.com, nonsense")
        self.assertIn("WARNING", log)
        self.assertIn("not readable", log)

    def test_running_it_twice_changes_nothing(self):
        self._sync()
        count, log = self._sync()
        self.assertEqual(count, 3)
        self.assertIn("0 of them newly written", log)
        self.assertEqual(self.repo.commits, [])


class WelcomeTests(unittest.TestCase):
    """A new subscriber's confirmation is the most recent digest itself."""

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.addCleanup(self.tmp.cleanup)
        self.digests = self.dir / "digest"
        self.digests.mkdir()
        (self.digests / "2026-11-02.md").write_text("# Older\n\nNot this one.\n")
        (self.digests / "2026-11-09.md").write_text(
            "# Weekly Literature Digest\n\n### 1. A paper about engagers\n\n"
            "[10.1158/1535-7163.MCT-25-1542](https://doi.org/10.1158/1535-7163.MCT-25-1542)\n"
        )

    def digest(self):
        return ml.latest_digest(self.digests)

    def test_the_newest_digest_is_the_one_sent(self):
        stamp, body = self.digest()
        self.assertEqual(stamp, "2026-11-09")
        self.assertIn("A paper about engagers", body)
        self.assertNotIn("Not this one", body)

    def test_no_digest_at_all_is_not_an_error(self):
        self.assertIsNone(ml.latest_digest(self.dir / "nothing"))

    def test_a_welcome_carries_the_digest_and_a_way_out(self):
        subject, text, html = ml.welcome_message(
            self.digest(), "added", "pod@example.com"
        )
        self.assertIn("2026-11-09", subject)
        self.assertIn("You're on the list", text)
        self.assertIn("9 November 2026", text)
        self.assertIn("A paper about engagers", text)
        self.assertIn("unsubscribe", text.lower())
        # Rendered, not raw: the markdown link becomes a link.
        self.assertIn("<h3>", html)
        self.assertIn('href="https://doi.org/10.1158/1535-7163.MCT-25-1542"', html)
        self.assertNotIn("### 1.", html)

    def test_writing_in_twice_still_gets_the_digest(self):
        subject, text, _ = ml.welcome_message(
            self.digest(), "already", "pod@example.com"
        )
        self.assertIn("Already subscribed", subject)
        self.assertIn("in case it went astray", text)
        self.assertIn("A paper about engagers", text)

    def test_with_no_digest_the_short_note_goes_instead(self):
        subject, text, html = ml.welcome_message(None, "added", "pod@example.com")
        self.assertEqual(subject, ml.SUBJECTS["added"])
        self.assertIn("You're on the list", text)
        self.assertIsNone(html)

    def test_a_date_that_is_not_a_date_is_left_alone(self):
        self.assertEqual(ml.spoken_date("2026-11-09"), "9 November 2026")
        self.assertEqual(ml.spoken_date("draft"), "draft")


class DeferredWelcomeTests(unittest.TestCase):
    """Recording the change and sending the digest happen in different steps."""

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.addCleanup(self.tmp.cleanup)
        for patch in (
            mock.patch.dict(
                "os.environ",
                {"DIGEST_RECIPIENTS": LEGACY, "GMAIL_APP_PASSWORD": "x"},
            ),
            mock.patch.object(mailbox, "drop_dir", lambda: self.dir / "drop"),
        ):
            patch.start()
            self.addCleanup(patch.stop)
        self.labelled: list[str] = []
        self.sent: list[tuple] = []
        self.extras: list[dict] = []

    def _patches(self, sending: bool = True, labelling: bool = True):
        def mark(uid, label=None):
            if labelling:
                self.labelled.append(uid)
            return labelling

        def reply(address, subject, body, html=None, **kwargs):
            self.sent.append((address, subject, body))
            self.extras.append(kwargs)
            return sending

        return (
            _patch_repo(FakeRepo(self.dir)),
            mock.patch.object(mailbox, "mark_uid", mark),
            mock.patch.object(mailbox, "reply_to", reply),
        )

    def _run(self, requests, *, sending: bool = True):
        a, b, c = self._patches(sending=sending)
        with a, b, c:
            return mailbox.handle_list_requests(requests)

    def test_a_new_subscriber_is_left_for_the_welcome_step(self):
        recorded, welcoming = self._run(
            [{"uid": "1", "address": "new@example.com", "wants": "subscribe"}]
        )
        self.assertEqual((recorded, welcoming), (1, 1))
        # Nothing sent and nothing labelled yet — that is the welcome's job.
        self.assertEqual(self.sent, [])
        self.assertEqual(self.labelled, [])
        self.assertEqual([e["uid"] for e in mailbox.welcomes_pending()], ["1"])

    def test_writing_in_twice_gets_the_note_and_not_the_digest_again(self):
        # WELCOME_OUTCOMES used to include "already", so a retry — or a label
        # that did not take — sent the whole ~100 KB digest a second time.
        recorded, welcoming = self._run(
            [{"uid": "3", "address": "ray@example.com", "wants": "subscribe"}]
        )
        self.assertEqual((recorded, welcoming), (1, 0))
        self.assertEqual(self.labelled, ["3"])
        self.assertIn("Already subscribed", self.sent[0][1])
        self.assertIn("already on the list", self.sent[0][2].lower())
        self.assertLess(len(self.sent[0][2]), 500, "that is a digest, not a note")
        self.assertEqual(mailbox.welcomes_pending(), [])

    def test_someone_leaving_is_answered_at_once(self):
        recorded, welcoming = self._run(
            [{"uid": "2", "address": "ben@example.net", "wants": "unsubscribe"}]
        )
        self.assertEqual((recorded, welcoming), (1, 0))
        self.assertEqual(self.labelled, ["2"])
        self.assertIn("Unsubscribed", self.sent[0][1])
        self.assertEqual(mailbox.welcomes_pending(), [])

    def test_the_welcome_step_sends_the_digest_and_then_labels(self):
        self._run([{"uid": "1", "address": "new@example.com", "wants": "subscribe"}])
        digests = self.dir / "digest"
        digests.mkdir()
        (digests / "2026-11-09.md").write_text("# Digest\n\nA paper.\n")
        a, b, c = self._patches()
        with a, b, c, mock.patch.object(ml, "DIGEST_DIR", digests):
            self.assertEqual(mailbox.send_welcomes(), 1)
        self.assertEqual(self.labelled, ["1"])
        address, subject, body = self.sent[0]
        self.assertEqual(address, "new@example.com")
        self.assertIn("2026-11-09", subject)
        self.assertIn("A paper", body)

    def test_a_welcome_whose_mail_cannot_be_labelled_is_not_sent(self):
        # The label comes first now. A refused label used to look like success,
        # so the request was found again by every poll for a fortnight and the
        # digest went out each time; not sending costs one welcome to someone
        # who is on the list either way.
        self._run([{"uid": "1", "address": "new@example.com", "wants": "subscribe"}])
        a, b, c = self._patches(labelling=False)
        with a, b, c:
            self.assertEqual(mailbox.send_welcomes(), 0)
        self.assertEqual(self.sent, [])

    def test_a_welcome_that_cannot_be_sent_is_not_sent_again(self):
        # Labelled before the send, so the fortnight of retries cannot happen.
        # They are subscribed, and Sunday's digest arrives as normal.
        self._run([{"uid": "1", "address": "new@example.com", "wants": "subscribe"}])
        a, b, c = self._patches(sending=False)
        with a, b, c:
            self.assertEqual(mailbox.send_welcomes(), 0)
        self.assertEqual(self.labelled, ["1"])

    def test_a_welcome_carries_the_list_headers_and_threads(self):
        self._run(
            [
                {
                    "uid": "1",
                    "address": "new@example.com",
                    "wants": "subscribe",
                    "message_id": "<abc123@mail.gmail.com>",
                }
            ]
        )
        digests = self.dir / "digest"
        digests.mkdir()
        (digests / "2026-11-09.md").write_text("# Digest\n\nA paper.\n")
        a, b, c = self._patches()
        with a, b, c, mock.patch.object(ml, "DIGEST_DIR", digests):
            self.assertEqual(mailbox.send_welcomes(), 1)
        self.assertEqual(self.extras[0]["unsubscribe"], send_email.SENDER)
        self.assertEqual(self.extras[0]["in_reply_to"], "<abc123@mail.gmail.com>")

    def test_an_answer_threads_under_the_request(self):
        self._run(
            [
                {
                    "uid": "2",
                    "address": "ben@example.net",
                    "wants": "unsubscribe",
                    "message_id": "<xyz@mail.gmail.com>",
                }
            ]
        )
        self.assertEqual(self.extras[0]["in_reply_to"], "<xyz@mail.gmail.com>")

    def test_nothing_pending_sends_nothing(self):
        self.assertEqual(mailbox.send_welcomes(), 0)


class MessageShapeTests(unittest.TestCase):
    """One message per subscriber, with a real To: and a way out in the headers.

    The digest used to be one multipart message with every subscriber in a
    blind envelope and `To: sciencetldrpod@gmail.com` — which hid nobody's
    address from anybody who was not on it, and is the shape spam filters
    score hardest against.
    """

    def _sent(self, refuse: dict | None = None, **kwargs) -> dict:
        captured: dict = {}

        class FakeSMTP:
            def __enter__(inner):  # noqa: N805
                return inner

            def __exit__(inner, *exc):  # noqa: N805
                return False

            def login(inner, *a):  # noqa: N805
                pass

            def sendmail(inner, sender, recipients, raw):  # noqa: N805
                captured.update(sender=sender, recipients=recipients, raw=raw)
                # What smtplib really answers with: the recipients the server
                # would not take, and {} when it took them all.
                return dict(refuse or {})

        with mock.patch.dict("os.environ", {"GMAIL_APP_PASSWORD": "x"}):
            with mock.patch.object(send_email.smtplib, "SMTP_SSL", lambda *a, **k: FakeSMTP()):
                captured["returned"] = send_email.send(**kwargs)
        return captured

    def test_a_subscriber_sees_their_own_address_and_no_one_elses(self):
        sent = self._sent(
            subject="Digest",
            body_text="hello" + ml.footer(send_email.SENDER)[0],
            recipients=["a@example.com"],
            unsubscribe=send_email.SENDER,
        )
        parsed = email.message_from_string(sent["raw"], policy=email.policy.default)
        self.assertEqual(parsed["To"], "a@example.com")
        self.assertIsNone(parsed["Cc"])
        self.assertIsNone(parsed["Bcc"])
        self.assertNotIn("b@example.org", sent["raw"])
        # Decoded, because the parts are base64: a header check alone would
        # pass even if an address were sitting in the body.
        body = parsed.get_body(preferencelist=("plain",)).get_content()
        self.assertIn("unsubscribe", body.lower())

    def test_one_click_unsubscribe_is_in_the_headers(self):
        sent = self._sent(
            subject="Digest",
            body_text="hello",
            recipients=["a@example.com"],
            unsubscribe="pod@example.com",
        )
        parsed = email.message_from_string(sent["raw"], policy=email.policy.default)
        self.assertEqual(
            parsed["List-Unsubscribe"], "<mailto:pod@example.com?subject=unsubscribe>"
        )
        self.assertEqual(parsed["List-Unsubscribe-Post"], "List-Unsubscribe=One-Click")

    def test_an_ordinary_message_carries_no_list_headers(self):
        sent = self._sent(subject="PDF needed", body_text="hello", recipients=["ray@example.com"])
        parsed = email.message_from_string(sent["raw"], policy=email.policy.default)
        self.assertIsNone(parsed["List-Unsubscribe"])

    def test_an_answer_threads_under_the_message_it_answers(self):
        sent = self._sent(
            subject="Subscribed",
            body_text="hello",
            recipients=["a@example.com"],
            in_reply_to="<CAF=abc123@mail.gmail.com>",
        )
        parsed = email.message_from_string(sent["raw"], policy=email.policy.default)
        self.assertEqual(parsed["In-Reply-To"], "<CAF=abc123@mail.gmail.com>")
        self.assertEqual(parsed["References"], "<CAF=abc123@mail.gmail.com>")

    def test_a_message_id_that_is_not_one_is_left_out(self):
        # It comes off a message somebody else wrote, so the shape is checked
        # before it goes anywhere near a header: a newline in there would be
        # a header injection, and a threadless reply is no loss.
        for forged in ("<a@b>\r\nBcc: victim@example.com", "not-an-id", ""):
            with self.subTest(value=forged[:20]):
                sent = self._sent(
                    subject="Subscribed",
                    body_text="hello",
                    recipients=["a@example.com"],
                    in_reply_to=forged,
                )
                parsed = email.message_from_string(sent["raw"], policy=email.policy.default)
                self.assertIsNone(parsed["In-Reply-To"])
                self.assertIsNone(parsed["Bcc"])

    def test_a_refused_recipient_is_counted_out_loud(self):
        # sendmail() answers with the recipients it could not deliver to; the
        # return value was dropped, so a dead address was never noticed.
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            refused = self._sent(
                subject="Digest",
                body_text="hello",
                recipients=["a@example.com", "gone@example.org"],
                refuse={"gone@example.org": (550, b"5.1.1 no such user gone@example.org")},
            )
        self.assertEqual(refused["returned"], 1)
        self.assertIn("1 of 2 recipient(s) refused", out.getvalue())
        self.assertNotIn("@", out.getvalue())

    def test_a_pdf_request_still_names_its_recipient(self):
        sent = self._sent(
            subject="PDF needed", body_text="hello", recipients=["ray@example.com"]
        )
        parsed = email.message_from_string(sent["raw"], policy=email.policy.default)
        self.assertEqual(parsed["To"], "ray@example.com")


class DigestSendTests(unittest.TestCase):
    """One message per subscriber, and one failure is not the whole send."""

    def _run(self, recipients: list[str], refuse: set[str] = frozenset()):
        sent: list[dict] = []

        def fake_send(**kwargs):
            if set(kwargs["recipients"]) & set(refuse):
                raise send_email.smtplib.SMTPRecipientsRefused(
                    {address: (550, b"5.1.1 no such user") for address in kwargs["recipients"]}
                )
            sent.append(kwargs)
            return 0

        out = io.StringIO()
        with tempfile.TemporaryDirectory() as tmp:
            digest = Path(tmp) / "2026-11-15.md"
            digest.write_text("# Digest\n\nA paper.\n", encoding="utf-8")
            env = {"GMAIL_APP_PASSWORD": "x", "DIGEST_FILE": str(digest)}
            with mock.patch.dict("os.environ", env):
                with mock.patch.object(ml, "recipients", lambda: recipients):
                    with mock.patch.object(send_email, "send", fake_send):
                        with contextlib.redirect_stdout(out):
                            email_digest.main()
        return sent, out.getvalue()

    def test_each_subscriber_gets_their_own_message(self):
        people = ["a@example.com", "b@example.org"]
        sent, log = self._run(people)
        self.assertEqual([call["recipients"] for call in sent], [[p] for p in people])
        self.assertTrue(all(call["unsubscribe"] == send_email.SENDER for call in sent))
        self.assertNotIn("@", log)

    def test_one_refused_subscriber_does_not_stop_the_others(self):
        sent, log = self._run(["a@example.com", "b@example.org"], refuse={"a@example.com"})
        self.assertEqual([call["recipients"] for call in sent], [["b@example.org"]])
        self.assertIn("1 of 2", log)
        self.assertNotIn("@", log)


class LabelTests(unittest.TestCase):
    """A Gmail label that was refused must not read as one that was stored.

    An unlabelled message is found again by every later poll, which is how one
    welcome became a fortnight of them.
    """

    def test_a_refused_label_is_not_reported_as_success(self):
        self.assertTrue(mailbox._label(FakeIMAP("OK"), b"7", mailbox.LABEL_PROCESSED))
        self.assertFalse(mailbox._label(FakeIMAP("NO"), b"7", mailbox.LABEL_PROCESSED))

    def test_mark_uid_carries_the_refusal_up_to_its_caller(self):
        for status, expected in (("OK", True), ("NO", False)):
            with self.subTest(status=status):
                fake = FakeIMAP(status)
                with mock.patch.dict("os.environ", {"GMAIL_APP_PASSWORD": "x"}):
                    with mock.patch.object(
                        mailbox.imaplib, "IMAP4_SSL", lambda host: fake
                    ):
                        self.assertIs(mailbox.mark_uid("7"), expected)
                self.assertEqual(fake.commands[0][0], "STORE")


class CollectingTests(unittest.TestCase):
    """What the standard-library pass takes off a subscribe mail."""

    RAW = (
        b"From: Someone <someone@victim.com>\r\n"
        b"Subject: subscribe\r\n"
        b"Message-ID: <abc123@mail.gmail.com>\r\n"
        b"Authentication-Results: mx.google.com; dkim=pass header.i=@victim.com;\r\n"
        b" dmarc=pass (p=NONE) header.from=victim.com\r\n"
        b"\r\n"
    )

    def test_a_request_carries_the_message_id_so_the_answer_can_thread(self):
        found = mailbox._collect_list_requests(FakeMailbox(self.RAW))
        self.assertEqual(
            found,
            [
                {
                    "uid": "7",
                    "address": "someone@victim.com",
                    "wants": "subscribe",
                    "subject": "subscribe",
                    "message_id": "<abc123@mail.gmail.com>",
                }
            ],
        )

    def test_a_request_gmail_did_not_vouch_for_is_rejected(self):
        forged = self.RAW.replace(b"mx.google.com", b"mail.attacker.net")
        fake = FakeMailbox(forged)
        self.assertEqual(mailbox._collect_list_requests(fake), [])
        self.assertIn("STORE", [command[0] for command in fake.commands])


class LogHygieneTests(unittest.TestCase):
    """A refused address must never reach this repository's public Actions log.

    GitHub masks the whole DIGEST_RECIPIENTS secret, not one address out of it,
    and smtplib puts every address it could not deliver to in the exception's
    own string form: `{'someone@example.com': (550, b'...')}`.
    """

    ADDRESS = "someone@example.com"

    def _refused(self, **kwargs):
        raise send_email.smtplib.SMTPRecipientsRefused(
            {self.ADDRESS: (550, b"5.1.1 no such user someone@example.com")}
        )

    def test_a_refused_reply_names_the_failure_not_the_recipient(self):
        out = io.StringIO()
        with mock.patch.dict("os.environ", {"GMAIL_APP_PASSWORD": "x"}):
            with mock.patch.object(send_email, "send", self._refused):
                with contextlib.redirect_stdout(out):
                    self.assertFalse(mailbox.reply_to(self.ADDRESS, "Subscribed", "hello"))
        self.assertNotIn("@", out.getvalue())
        self.assertIn("SMTPRecipientsRefused", out.getvalue())

    def test_a_refused_one_off_answer_names_no_address_either(self):
        out = io.StringIO()
        env = {"GMAIL_APP_PASSWORD": "x", "PDF_REQUEST_TO": self.ADDRESS}
        with mock.patch.dict("os.environ", env):
            with mock.patch.object(send_email, "send", self._refused):
                with contextlib.redirect_stdout(out):
                    self.assertFalse(mailbox.answer("one-off", "body"))
        self.assertNotIn("@", out.getvalue())

    def test_a_digest_nobody_accepts_fails_without_naming_anyone(self):
        # Uncaught, this was a traceback carrying every subscriber's address.
        with tempfile.TemporaryDirectory() as tmp:
            digest = Path(tmp) / "2026-11-15.md"
            digest.write_text("# Digest\n\nA paper.\n", encoding="utf-8")
            out = io.StringIO()
            env = {"GMAIL_APP_PASSWORD": "x", "DIGEST_FILE": str(digest)}
            with mock.patch.dict("os.environ", env):
                with mock.patch.object(ml, "recipients", lambda: [self.ADDRESS]):
                    with mock.patch.object(send_email, "send", self._refused):
                        with contextlib.redirect_stdout(out):
                            with self.assertRaises(SystemExit) as caught:
                                email_digest.main()
        self.assertNotIn("@", out.getvalue())
        self.assertNotIn("@", str(caught.exception))
        self.assertIn("SMTPRecipientsRefused", out.getvalue())


if __name__ == "__main__":
    unittest.main()
