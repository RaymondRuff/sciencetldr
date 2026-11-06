"""The dialogue speaks few figures, and says what the rest amount to.

Episode 95 read values off panels — eight in one turn, twenty-two decimals in
eleven minutes — which is the habit these limits exist to break. See
prompts/host_dialogue.md, "Numbers — few, and chosen".

Run: uv run python -m unittest discover tests
"""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import routine_tools as rt  # noqa: E402

FILLER = (
    "They reported the result and we talked about what it does and does not "
    "support, at some length, without reaching for a stronger word. "
)


def turns(*texts: str) -> list[dict]:
    speakers = ("Nadia", "Theo")
    return [{"speaker": speakers[i % 2], "text": t} for i, t in enumerate(texts)]


def padded(*texts: str) -> list[dict]:
    """A script long enough for the spoken-length window, with no stray figures."""
    built = turns(
        "Hi, and welcome to Science TLDR. I'm Nadia.",
        "And I'm Theo.",
        *texts,
    )
    while rt.spoken_chars(built) < rt.TARGET_MIN_CHARS:
        built.append({"speaker": "Nadia" if len(built) % 2 else "Theo", "text": FILLER * 4})
    return built


class FigurePhraseTests(unittest.TestCase):
    def test_a_quantity_counts(self):
        found = rt.figure_phrases(turns("Albumin at fourteen point three picomolar."))
        self.assertEqual([p for _, p in found], ["fourteen point three"])

    def test_small_prose_numbers_do_not_count(self):
        found = rt.figure_phrases(turns("Two things stand out, and the third is the control."))
        self.assertEqual(found, [])

    def test_the_doi_sign_off_does_not_count(self):
        found = rt.figure_phrases(
            turns("The D-O-I is ten dot one one one one slash four four five five.")
        )
        self.assertEqual(found, [])

    def test_episode_callbacks_and_years_do_not_count(self):
        found = rt.figure_phrases(
            turns("We looked at this in episode seventy-four, back in twenty twenty-four.")
        )
        self.assertEqual(found, [])

    def test_a_figure_is_tied_to_its_turn(self):
        found = rt.figure_phrases(
            turns("Nothing numeric here.", "About ninety-five picomolar.")
        )
        self.assertEqual(found, [(1, "ninety five")])  # hyphens normalise to spaces


class RegisterTests(unittest.TestCase):
    def check(self, turns_):
        return rt.check_number_register(turns_)

    def test_a_conversational_script_passes_clean(self):
        errors, warnings = self.check(turns(
            "The first rate was close to two, and the second about twice as fast.",
            "So it barely moved in the control?",
            "Right — within noise. The binding is low picomolar either way.",
            "And the headline figure?",
            "Ninety-five picomolar, which is tight enough that another round would "
            "be hard to justify.",
        ))
        self.assertEqual((errors, warnings), ([], []))

    def test_over_the_budget_warns(self):
        many = turns(*[f"That one came out at {rt.number_words(n)} picomolar." for n in range(30, 60)])
        errors, warnings = self.check(many)
        self.assertEqual(errors, [])
        self.assertTrue(any("budget of 25" in w for w in warnings), warnings)

    def test_a_recital_is_refused(self):
        many = turns(*[f"That one came out at {rt.number_words(n)} picomolar." for n in range(30, 90)])
        errors, _ = self.check(many)
        self.assertTrue(any("budget of 25" in e for e in errors), errors)

    def test_a_turn_that_stacks_values_is_flagged(self):
        errors, warnings = self.check(turns(
            "Peak two point eight against two point five, and the ratio is zero point five."
        ))
        self.assertTrue(any("stacks" in w for w in warnings), warnings)
        self.assertEqual(errors, [])

    def test_a_turn_reading_a_whole_panel_is_refused(self):
        errors, _ = self.check(turns(
            "Zero point five, zero point nine, two point four, ninety-three point nine, "
            "eighty-one point seven and twenty-nine point three."
        ))
        self.assertTrue(any("stacks" in e for e in errors), errors)

    def test_decimals_are_budgeted(self):
        few = turns(*[f"It was {rt.number_words(n)} point five." for n in range(30, 38)])
        errors, warnings = self.check(few)
        self.assertTrue(any("decimals spoken" in w for w in warnings), warnings)
        many = turns(*[f"It was {rt.number_words(n)} point five." for n in range(30, 45)])
        errors, _ = self.check(many)
        self.assertTrue(any("decimals spoken" in e for e in errors), errors)

    def test_statistical_apparatus_is_refused(self):
        for phrase in (
            "the confidence interval ran from zero to two",
            "the p-value was under zero point zero five",
            "one standard deviation either side",
            "thirty percent plus or minus four",
        ):
            errors, _ = self.check(turns(phrase))
            self.assertTrue(any("apparatus" in e for e in errors), (phrase, errors))

    def test_talking_about_spread_in_words_is_fine(self):
        errors, warnings = self.check(turns(
            "The curves overlap inside their error bars, so that separation isn't real.",
            "And the range is wide enough that no effect at all is still on the table.",
        ))
        self.assertEqual((errors, warnings), ([], []))


class ValidateTests(unittest.TestCase):
    def test_validate_surfaces_the_register_errors(self):
        script = {
            "issue": 7, "writer": "routine", "paper_source": "test", "checked": False,
            "callbacks": [], "verification_changes": [],
            "show_notes": "**[A paper](x)**\n\n*J, 2026*\n\nDOI: [10.1/x](https://doi.org/10.1/x)\n\n"
                          "**Question:** Q?\n\n**Answer:** A.\n\n**Three takeaways**\n\n"
                          "1. One.\n2. Two.\n3. Three.\n",
            "runs": [{"role": "writer", "started": "2026-11-06T08:00:00Z",
                      "finished": "2026-11-06T08:30:00Z", "safeguard_stops": 0}],
            "turns": padded("The p-value was under zero point zero five."),
        }
        errors, _ = rt.validate(script, "draft")
        self.assertTrue(any("apparatus" in e for e in errors), errors)

    def test_a_clean_script_still_validates(self):
        script = {
            "issue": 7, "writer": "routine", "paper_source": "test", "checked": False,
            "callbacks": [], "verification_changes": [],
            "show_notes": "**[A paper](x)**\n\n*J, 2026*\n\nDOI: [10.1/x](https://doi.org/10.1/x)\n\n"
                          "**Question:** Q?\n\n**Answer:** A.\n\n**Three takeaways**\n\n"
                          "1. One.\n2. Two.\n3. Three.\n",
            "runs": [{"role": "writer", "started": "2026-11-06T08:00:00Z",
                      "finished": "2026-11-06T08:30:00Z", "safeguard_stops": 0}],
            "turns": padded("It was about twice as fast, and low picomolar either way."),
        }
        self.assertEqual(rt.validate(script, "draft")[0], [])


class Episode95Tests(unittest.TestCase):
    """The script that prompted this change would now be refused."""

    PATH = ROOT / "generated" / "routine" / "issue-90.script.json"

    @unittest.skipUnless(PATH.is_file(), "episode 95's script is not in this checkout")
    def test_it_is_refused_for_reciting(self):
        turns_ = json.loads(self.PATH.read_text(encoding="utf-8"))["turns"]
        errors, _ = rt.check_number_register(turns_)
        self.assertTrue(any("budget of 25" in e for e in errors), errors)
        self.assertTrue(any("decimals spoken" in e for e in errors), errors)
        self.assertTrue(any("stacks" in e for e in errors), errors)


if __name__ == "__main__":
    unittest.main()
