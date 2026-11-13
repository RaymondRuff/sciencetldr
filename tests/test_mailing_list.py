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

import mailing_list as ml  # noqa: E402
import pdf_mailbox as mailbox  # noqa: E402
import send_email  # noqa: E402

LEGACY = "ray@example.com,anna@example.org, ben@example.net"


class FakeRepo:
    """Stands in for a clone of the private papers repository."""

    def __init__(self, directory: Path, *, fails: bool = False) -> None:
        self.dir = directory
        self.fails = fails
        self.commits: list[tuple[str, tuple[str, ...]]] = []

    def commit(self, message: str, paths: tuple[str, ...] = ("papers",)) -> bool:
        if self.fails:
            raise RuntimeError("push rejected")
        self.commits.append((message, paths))
        return True


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

    def test_an_unreachable_repository_falls_back_to_the_secret(self):
        # An outage in the private repository must not stop the digest, and
        # must not silently drop the people only the secret knows about.
        def boom():
            raise RuntimeError("clone failed")

        with mock.patch.object(ml, "_repo", boom):
            self.assertEqual(
                ml.recipients(),
                ["anna@example.org", "ben@example.net", "ray@example.com"],
            )

    def test_with_no_secret_and_no_repository_it_raises(self):
        def boom():
            raise RuntimeError("clone failed")

        with mock.patch.dict("os.environ", {"DIGEST_RECIPIENTS": ""}):
            with mock.patch.object(ml, "_repo", boom):
                with self.assertRaises(RuntimeError):
                    ml.recipients()

    def test_chunks_keeps_every_address_once(self):
        addresses = [f"p{n}@example.com" for n in range(200)]
        batches = ml.chunks(addresses)
        self.assertEqual(sum(len(b) for b in batches), 200)
        self.assertEqual(max(len(b) for b in batches), ml.CHUNK)
        self.assertEqual(sorted(a for b in batches for a in b), sorted(addresses))


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

    def _patches(self, sending: bool = True):
        return (
            _patch_repo(FakeRepo(self.dir)),
            mock.patch.object(
                mailbox, "mark_uid", lambda uid, label=None: self.labelled.append(uid)
            ),
            mock.patch.object(
                mailbox,
                "reply_to",
                lambda address, subject, body, html=None: (
                    self.sent.append((address, subject, body)) or sending
                )
                if sending
                else False,
            ),
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

    def test_a_failed_welcome_leaves_the_mail_for_the_next_poll(self):
        # Unlabelled, so the request is found again; it reads as "already" and
        # the same digest goes out. Better half an hour late than never.
        self._run([{"uid": "1", "address": "new@example.com", "wants": "subscribe"}])
        a, b, c = self._patches(sending=False)
        with a, b, c:
            self.assertEqual(mailbox.send_welcomes(), 0)
        self.assertEqual(self.labelled, [])

    def test_nothing_pending_sends_nothing(self):
        self.assertEqual(mailbox.send_welcomes(), 0)


class BlindCopyTests(unittest.TestCase):
    """The digest must not show one subscriber's address to another."""

    def _sent(self, **kwargs) -> dict:
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

        with mock.patch.dict("os.environ", {"GMAIL_APP_PASSWORD": "x"}):
            with mock.patch.object(send_email.smtplib, "SMTP_SSL", lambda *a, **k: FakeSMTP()):
                send_email.send(**kwargs)
        return captured

    def test_blind_copies_name_nobody_in_the_headers(self):
        people = ["a@example.com", "b@example.org"]
        sent = self._sent(
            subject="Digest",
            body_text="hello" + ml.footer(send_email.SENDER)[0],
            recipients=people,
            bcc=True,
        )
        # Still delivered to everyone — the envelope decides that, not the
        # headers, which is the whole mechanism.
        self.assertEqual(sent["recipients"], people)
        parsed = email.message_from_string(sent["raw"], policy=email.policy.default)
        self.assertEqual(parsed["To"], send_email.SENDER)
        self.assertIsNone(parsed["Cc"])
        self.assertIsNone(parsed["Bcc"])
        # Decoded, because the parts are base64: a header check alone would
        # pass even if the addresses were sitting in the body.
        body = parsed.get_body(preferencelist=("plain",)).get_content()
        for address in people:
            self.assertNotIn(address, body)
        self.assertIn("unsubscribe", body.lower())

    def test_without_bcc_the_recipients_are_named_as_before(self):
        sent = self._sent(
            subject="PDF needed", body_text="hello", recipients=["ray@example.com"]
        )
        parsed = email.message_from_string(sent["raw"], policy=email.policy.default)
        self.assertEqual(parsed["To"], "ray@example.com")


if __name__ == "__main__":
    unittest.main()
