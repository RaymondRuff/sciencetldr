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

    def test_a_valid_draft_is_used(self):
        self.write(7, a_valid_script(7))
        result = ge.routine_script(7)
        self.assertIsNotNone(result)
        turns, changes, source = result
        self.assertEqual(turns[0]["speaker"], "Nadia")
        self.assertEqual(changes, [])
        self.assertEqual(source, "bundle:issue-7")

    def test_a_checked_script_carries_its_corrections(self):
        self.write(7, a_valid_script(7, checked=True))
        _, changes, _ = ge.routine_script(7)
        self.assertEqual(changes, ["fixed a number"])

    def test_a_script_that_fails_the_validator_is_refused(self):
        # Digits in the dialogue: the voices would read them wrong, so this
        # must fall through to the paid path rather than be synthesised.
        script = a_valid_script(7)
        script["turns"][-1]["text"] = "The hazard ratio was 1.27 in that arm."
        self.write(7, script)
        self.assertIsNone(ge.routine_script(7))

    def test_a_truncated_file_is_refused_not_raised(self):
        self.write(7, '{"issue": 7, "turns": [')
        self.assertIsNone(ge.routine_script(7))

    def test_a_script_for_another_issue_is_not_picked_up(self):
        self.write(7, a_valid_script(7))
        self.assertIsNone(ge.routine_script(8))


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
