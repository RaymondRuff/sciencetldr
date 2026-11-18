"""The two rules the prompt alone could not hold: the sign-off, and the length.

Episode ninety-nine closed with "See you Friday." Nothing in the prompt asked
for a day — the model inferred it from the weekly rhythm in the cold open, and
it was a promise the pipeline had not made, since a one-off can land on any day.
A prose instruction would be forgotten the same way, so the validator enforces
it; see check_sign_off().

The length test is a drift guard. The prompt told the model to write
10,200-10,800 spoken characters while the validator demanded 11,000-11,600 —
the ten-point-two-to-ten-point-eight *minutes* written down as characters. Every
script was failing short and being stretched to fit a target nobody had stated.

Run: uv run python -m unittest discover tests
"""
from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import routine_tools as rt  # noqa: E402

PROMPT = ROOT / "prompts" / "host_dialogue.md"


def closing(*texts: str) -> list[dict]:
    """A minimal script whose last turns are the ones given."""
    turns = [{"speaker": "Nadia", "text": "Hi, and welcome to Science TLDR. I'm Nadia."}]
    for i, text in enumerate(texts):
        turns.append({"speaker": "Theo" if i % 2 else "Nadia", "text": text})
    return turns


class SignOffTests(unittest.TestCase):
    def test_the_line_that_started_this_is_rejected(self):
        errors = rt.check_sign_off(closing("That's J-C-I Insight.", "See you Friday."))
        self.assertEqual(len(errors), 1)
        self.assertIn("Friday", errors[0])
        self.assertIn("one-off can land on any day", errors[0])

    def test_a_close_that_promises_nothing_passes(self):
        for line in (
            "Thanks for listening.",
            "Until the next one.",
            "See you next week.",
            "That's all from us.",
        ):
            with self.subTest(line=line):
                self.assertEqual(rt.check_sign_off(closing("DOI line.", line)), [])

    def test_the_plural_and_the_lower_case_are_caught_too(self):
        self.assertTrue(rt.check_sign_off(closing("DOI line.", "Back on mondays, as ever.")))
        self.assertTrue(rt.check_sign_off(closing("DOI line.", "More on FRIDAY.")))

    def test_one_error_per_day_however_often_it_appears(self):
        errors = rt.check_sign_off(closing("Friday then.", "Friday it is. See you Friday."))
        self.assertEqual(len(errors), 1)

    def test_the_cold_opens_strand_framing_stays_legal(self):
        # Required by The strands section, and the reason this is scoped to
        # the closing turns rather than the whole script.
        turns = closing(
            "As we do on Fridays, we're turning to the science subreddit.",
            "And this was sitting at the top.",
            "That's J-C-I Insight, this year.",
            "Thanks for listening.",
        )
        self.assertEqual(rt.check_sign_off(turns), [])

    def test_a_weekday_in_the_body_of_the_episode_is_not_a_sign_off(self):
        turns = closing(
            "They sampled on Tuesdays and Thursdays for six weeks.",
            "Why those days?",
            "Thanks for listening.",
            "Until next time.",
        )
        self.assertEqual(rt.check_sign_off(turns), [])

    def test_validate_reports_it_with_everything_else(self):
        script = {"turns": closing("That's J-C-I Insight.", "See you Friday.")}
        errors, _ = rt.validate(script)
        self.assertTrue(any("sign-off names a day" in e for e in errors))


class BalanceTests(unittest.TestCase):
    """Theo's weight is measured, so the writer hears about it before the checker."""

    def script(self, theo_words: int, nadia_words: int, theo_turns: int = 20) -> list[dict]:
        turns = []
        per = max(theo_words // theo_turns, 1)
        for _ in range(theo_turns):
            turns.append({"speaker": "Nadia", "text": " ".join(["word"] * (nadia_words // theo_turns))})
            turns.append({"speaker": "Theo", "text": " ".join(["word"] * per)})
        return turns

    def test_mondays_balance_would_have_been_flagged(self):
        # Five hundred and sixteen words to Nadia's one thousand four hundred
        # and twenty-one, across thirty-four turns: twenty-seven per cent.
        warnings = rt.check_balance(self.script(516, 1421, theo_turns=34))
        self.assertEqual(len(warnings), 1)
        self.assertIn("27%", warnings[0])
        self.assertIn("34 turns", warnings[0])

    def test_a_third_of_the_words_passes(self):
        self.assertEqual(rt.check_balance(self.script(700, 1400)), [])

    def test_two_fifths_passes(self):
        self.assertEqual(rt.check_balance(self.script(840, 1260)), [])

    def test_it_is_a_warning_and_never_an_error(self):
        # A good episode must not be blocked over a share nobody can dial.
        script = {"turns": self.script(516, 1421, theo_turns=34)}
        errors, warnings = rt.validate(script)
        self.assertTrue(any("Theo has" in w for w in warnings))
        self.assertFalse(any("Theo has" in e for e in errors))

    def test_an_empty_script_is_not_a_crash(self):
        self.assertEqual(rt.check_balance([]), [])


class SpokenDoiTests(unittest.TestCase):
    """Forty seconds of digits that nobody writes down, and it's in the notes."""

    def turn(self, text: str) -> list[dict]:
        return [{"speaker": "Nadia", "text": text}]

    def test_the_line_from_mondays_episode_is_rejected(self):
        errors = rt.check_no_spoken_doi(self.turn(
            "That's J-C-I Insight, this year. D-O-I ten dot one one seven two "
            "slash j c i dot insight dot two zero five nine eight four."
        ))
        self.assertEqual(len(errors), 1)
        self.assertIn("name the journal and the year", errors[0])

    def test_the_spoken_spelling_is_what_gets_caught(self):
        # By the time a script exists the DOI has been expanded for the ear,
        # so a raw-DOI pattern alone would never see it.
        self.assertEqual(rt.DOI_RE.search("D-O-I ten dot one one seven two"), None)
        self.assertTrue(rt.check_no_spoken_doi(self.turn("D-O-I ten dot one")))

    def test_an_unspelled_doi_is_caught_as_well(self):
        self.assertTrue(rt.check_no_spoken_doi(self.turn("It's 10.1172/jci.insight.205984.")))

    def test_journal_and_year_is_the_whole_sign_off(self):
        self.assertEqual(
            rt.check_no_spoken_doi(self.turn("That was Molecular Cancer Therapeutics, this year.")),
            [],
        )

    def test_an_ordinary_sentence_is_not_a_doi(self):
        for line in ("The doily pattern in figure two.", "Two of the mice died."):
            with self.subTest(line=line):
                self.assertEqual(rt.check_no_spoken_doi(self.turn(line)), [])

    def test_validate_reports_it(self):
        script = {"turns": [
            {"speaker": "Nadia", "text": "Hi, and welcome to Science TLDR. I'm Nadia."},
            {"speaker": "Theo", "text": "And I'm Theo."},
            {"speaker": "Nadia", "text": "D-O-I ten dot one one seven two slash x."},
        ]}
        errors, _ = rt.validate(script)
        self.assertTrue(any("reads the DOI aloud" in e for e in errors))


class PromptContractTests(unittest.TestCase):
    """What the prompt tells the model must match what the validator enforces."""

    def text(self) -> str:
        return PROMPT.read_text(encoding="utf-8")

    def test_the_prompts_length_target_is_the_one_the_validator_accepts(self):
        stated = re.search(r"\*\*([\d,]+)–([\d,]+) characters\*\* of spoken text", self.text())
        self.assertIsNotNone(stated, "the prompt no longer states a character window")
        low, high = (int(g.replace(",", "")) for g in stated.groups())
        self.assertEqual((low, high), (rt.TARGET_MIN_CHARS, rt.TARGET_MAX_CHARS))

    def test_that_window_really_is_about_ten_minutes(self):
        # The original error was writing the minutes down as characters.
        for chars in (rt.TARGET_MIN_CHARS, rt.TARGET_MAX_CHARS):
            minutes = chars / rt.SPOKEN_CHARS_PER_MINUTE
            with self.subTest(chars=chars):
                self.assertGreater(minutes, 9.5)
                self.assertLess(minutes, 11.5)

    def test_the_prompt_warns_about_the_sign_off_rule(self):
        # A mechanical rule the model is never told about is a trap.
        self.assertIn("Never name a day of the week", self.text())

    def test_the_prompt_warns_about_the_doi_rule_too(self):
        self.assertIn("Never read the DOI aloud", self.text())

    def test_the_show_notes_still_carry_the_doi(self):
        # Dropping it from the dialogue only works because it survives there.
        notes = (ROOT / "prompts" / "show_notes.md").read_text(encoding="utf-8")
        self.assertIn("DOI", notes)
        self.assertIn("https://doi.org/", notes)


if __name__ == "__main__":
    unittest.main()
