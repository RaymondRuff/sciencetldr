"""The pipeline must be able to use a script a routine already wrote.

Run: uv run python -m unittest discover tests
"""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import generate_episode as ge  # noqa: E402
import routine_tools  # noqa: E402


SHOW_NOTES = """**[A paper](https://doi.org/10.1/x)**

*Journal of Things, 2026*

DOI: [10.1/x](https://doi.org/10.1/x)

**Question:** Does the treatment change the outcome in 120 patients?

**Answer:** It lowered the outcome by 12% (95% CI 4-20%), in one cohort without a control arm.

**Three takeaways**

1. The effect was 12% in 120 patients.
2. There was no control arm.
3. The authors call it preliminary.
"""


def a_valid_script(issue: int, *, checked: bool = False) -> dict:
    """The smallest script the validator accepts, built from its own rules."""
    turns = [
        {"speaker": "Nadia", "text": "Hello, and welcome to Science TLDR. I'm Nadia."},
        {"speaker": "Theo", "text": "And I'm Theo."},
    ]
    # Pad to the required spoken length with plain, speakable prose.
    filler = (
        "They reported the result and we talked about what it does and does "
        "not support, at some length, without reaching for a stronger word. "
    )
    body = filler * 4
    while routine_tools.spoken_chars(turns) < routine_tools.TARGET_MIN_CHARS:
        speaker = "Nadia" if len(turns) % 2 else "Theo"
        turns.append({"speaker": speaker, "text": body})
    script = {
        "issue": issue,
        "writer": "routine",
        "paper_source": "bundle:issue-" + str(issue),
        "show_notes": SHOW_NOTES,
        "checked": checked,
        "callbacks": [],
        "verification_changes": ["fixed a number"] if checked else [],
        "runs": [
            {
                "role": "writer",
                "started": "2026-11-04T01:00:00Z",
                "finished": "2026-11-04T01:20:00Z",
                "safeguard_stops": 0,
            }
        ],
        "turns": turns,
    }
    if checked:
        script["runs"].append(
            {
                "role": "checker",
                "started": "2026-11-04T02:00:00Z",
                "finished": "2026-11-04T02:20:00Z",
                "safeguard_stops": 0,
            }
        )
    return script


class RoutineHandoffTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self._saved = ge.ROUTINE_DIR
        ge.ROUTINE_DIR = Path(self._tmp.name)
        self.addCleanup(lambda: setattr(ge, "ROUTINE_DIR", self._saved))

    def write(self, issue: int, payload) -> Path:
        path = ge.routine_script_path(issue)
        path.write_text(
            payload if isinstance(payload, str) else json.dumps(payload),
            encoding="utf-8",
        )
        return path

    def test_no_script_is_not_an_error(self):
        self.assertIsNone(ge.routine_script(7))

    def test_a_checked_script_is_used(self):
        self.write(7, a_valid_script(7, checked=True))
        result = ge.routine_script(7)
        self.assertIsNotNone(result)
        turns, changes, source, notes = result
        self.assertEqual(turns[0]["speaker"], "Nadia")
        self.assertEqual(changes, ["fixed a number"])
        self.assertEqual(source, "bundle:issue-7")
        self.assertIn("**Three takeaways**", notes)

    def test_an_unchecked_draft_waits_for_the_checker(self):
        # The checker's push to main is what puts an episode into production;
        # a draft that reached main some other way must not skip it.
        self.write(7, a_valid_script(7))
        self.assertIsNone(ge.routine_script(7))

    def test_a_script_that_fails_the_validator_is_refused(self):
        # Digits in the dialogue: the voices would read them wrong.
        script = a_valid_script(7, checked=True)
        script["turns"][-1]["text"] = "The hazard ratio was 1.27 in that arm."
        self.write(7, script)
        self.assertIsNone(ge.routine_script(7))

    def test_a_truncated_file_is_refused_not_raised(self):
        self.write(7, '{"issue": 7, "turns": [')
        self.assertIsNone(ge.routine_script(7))

    def test_a_script_for_another_issue_is_not_picked_up(self):
        self.write(7, a_valid_script(7, checked=True))
        self.assertIsNone(ge.routine_script(8))


def an_issue(number: int, *labels: str) -> dict:
    return {
        "number": number,
        "title": f"Paper {number}",
        "labels": [{"name": name} for name in ("podcast-pending", *labels)],
        "body": "",
    }


class ScriptedIssueTests(unittest.TestCase):
    """A checked script on main is enough to make an episode, on its own.

    Issue #90's paper reached the show as an upload to the private papers
    repository, which the sweep's token could not open. The sweep then saw a
    `needs-pdf` Issue with no text, skipped it, and never used the checked
    script sitting on main.
    """

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        tmp = Path(self._tmp.name)
        saved = {
            name: getattr(ge, name)
            for name in ("ROOT", "ROUTINE_DIR", "GENERATED", "subprocess")
        }
        self.addCleanup(lambda: [setattr(ge, k, v) for k, v in saved.items()])
        ge.ROUTINE_DIR = tmp / "routine"
        ge.ROUTINE_DIR.mkdir()
        ge.GENERATED = tmp
        ge.ROOT = tmp

        class NoGit:
            @staticmethod
            def run(*args, **kwargs):
                return None

        ge.subprocess = NoGit  # process() checks out main before anything else

        self.resolved: list[int] = []
        saved_resolve = ge.paper_text.resolve

        def no_fetching(**kwargs):
            self.resolved.append(kwargs.get("issue_number"))
            return None

        ge.paper_text.resolve = no_fetching
        self.addCleanup(lambda: setattr(ge.paper_text, "resolve", saved_resolve))

    def write(self, issue: int, script: dict) -> None:
        ge.routine_script_path(issue).write_text(json.dumps(script), encoding="utf-8")

    def test_a_scripted_needs_pdf_issue_is_eligible_and_first(self):
        self.write(90, a_valid_script(90, checked=True))
        issues = [
            an_issue(40, "needs-pdf", "pdf-requested"),
            an_issue(85),
            an_issue(90, "needs-pdf", "pdf-requested"),
        ]
        saved = ge.paper_text.from_local_pdf
        ge.paper_text.from_local_pdf = lambda doi, number: None
        self.addCleanup(lambda: setattr(ge.paper_text, "from_local_pdf", saved))
        chosen = [i["number"] for i in ge.eligible_issues(issues, None, set())]
        self.assertEqual(chosen, [90, 85])

    def test_a_scripted_issue_needs_no_paper_text(self):
        self.write(90, a_valid_script(90, checked=True))
        outcome = ge.process(an_issue(90, "needs-pdf"), None, dry_run=True)
        self.assertEqual(outcome, ge.DRAFTED_UNPAID)
        self.assertEqual(self.resolved, [])

    def test_no_paid_attempt_left_means_no_fetch_and_no_spend(self):
        # An invalid script is no script. With the cap at zero the paid path
        # must not run, and there is no point fetching text it would feed.
        script = a_valid_script(85, checked=True)
        script["turns"][-1]["text"] = "It was 12 percent."
        self.write(85, script)
        outcome = ge.process(an_issue(85), None, dry_run=True, allow_paid=False)
        self.assertEqual(outcome, ge.WAITING)
        self.assertEqual(self.resolved, [])


class PublishSlotTests(unittest.TestCase):
    """Only a PR carrying audio may take the daily publish slot."""

    def setUp(self):
        self.calls: list[list[str]] = []
        self.files: dict[str, list[str]] = {}
        original = ge.gh

        def fake_gh(args):
            self.calls.append(args)
            if args[:2] == ["pr", "list"]:
                return json.dumps(
                    [
                        {
                            "number": 96,
                            "title": "Routine writer: draft script",
                            "headRefName": "episode/issue-90-chimeraffibodies",
                            "createdAt": "2026-11-04T01:00:00Z",
                        },
                        {
                            "number": 97,
                            "title": "Episode draft: a real one",
                            "headRefName": "episode/issue-90-real",
                            "createdAt": "2026-11-04T14:00:00Z",
                        },
                    ]
                )
            if args[:2] == ["pr", "view"]:
                paths = self.files.get(args[2], [])
                return json.dumps({"files": [{"path": x} for x in paths]})
            return ""

        ge.gh = fake_gh
        self.addCleanup(lambda: setattr(ge, "gh", original))

    def merged(self) -> list[str]:
        return [a[2] for a in self.calls if a[:2] == ["pr", "merge"]]

    def test_a_script_only_pr_does_not_take_the_slot(self):
        self.files["96"] = ["generated/routine/issue-90.script.json"]
        self.files["97"] = ["inbox/issue-90-real.mp3", "inbox/issue-90-real.transcript.txt"]
        ge.publish_next_draft()
        # The older PR is skipped even though its branch name matches.
        self.assertEqual(self.merged(), ["97"])

    def test_nothing_is_merged_when_no_pr_carries_audio(self):
        self.files["96"] = ["generated/routine/issue-90.script.json"]
        self.files["97"] = ["docs/notes.md"]
        ge.publish_next_draft()
        self.assertEqual(self.merged(), [])

    def test_an_unreadable_file_list_still_publishes(self):
        # A silent, permanent stop to auto-publishing is the worse failure.
        original = ge.gh

        def failing_view(args):
            if args[:2] == ["pr", "view"]:
                raise RuntimeError("unknown JSON field: files")
            return original(args)

        ge.gh = failing_view
        ge.publish_next_draft()
        self.assertEqual(self.merged(), ["96"])

    def test_audio_outside_inbox_does_not_count(self):
        self.files["96"] = ["docs/sample.mp3"]
        self.files["97"] = ["inbox/issue-90-real.MP3"]
        ge.publish_next_draft()
        self.assertEqual(self.merged(), ["97"])


if __name__ == "__main__":
    unittest.main()
