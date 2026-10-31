"""Tests for scripts/routine_tools.py.  Run: uv run python -m unittest discover tests"""
from __future__ import annotations

import copy
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import routine_tools as rt  # noqa: E402

FILLER = (
    "They measured the outcome in four separate cohorts and reported each one "
    "plainly, with the uncertainty attached, which is more than most papers do. "
)


def make_script(target: int = 11_300) -> dict:
    turns = [
        {"speaker": "Nadia", "text": "Hi, and welcome to Science TLDR. I'm Nadia."},
        {"speaker": "Theo", "text": "And I'm Theo."},
        {"speaker": "Nadia", "text": "And today we're looking at a cohort study."},
    ]
    speaker = "Theo"
    while rt.spoken_chars(turns) < target:
        turns.append({"speaker": speaker, "text": (FILLER * 4).strip()})
        speaker = "Nadia" if speaker == "Theo" else "Theo"
    return {
        "issue": 86,
        "writer": "routine",
        "paper_source": "test fixture",
        "checked": False,
        "callbacks": [],
        "verification_changes": [],
        "runs": [{"role": "writer", "started": "2026-11-06T14:03:00Z",
                  "finished": "2026-11-06T14:21:00Z", "safeguard_stops": 0}],
        "turns": turns,
    }


def checked(script: dict) -> dict:
    s = copy.deepcopy(script)
    s["checked"] = True
    s["verification_changes"] = ["Nadia said four cohorts; the paper reports three"]
    s["runs"].append({"role": "checker", "started": "2026-11-06T16:00:00Z",
                      "finished": "2026-11-06T16:30:00Z", "safeguard_stops": 1})
    return s


class SpokenForm(unittest.TestCase):
    def test_numbers(self):
        self.assertEqual(rt.spoken_form("12,779 genes"), "twelve thousand seven hundred seventy-nine genes")
        self.assertEqual(rt.spoken_form("0.1 nanomolar"), "zero point one nanomolar")
        self.assertEqual(rt.spoken_form("45%"), "forty-five percent")
        self.assertEqual(rt.spoken_form("1,000,000"), "one million")

    def test_years(self):
        self.assertEqual(rt.spoken_form("in 2024"), "in twenty twenty-four")
        self.assertEqual(rt.spoken_form("in 2007"), "in two thousand seven")
        self.assertEqual(rt.spoken_form("in 1905"), "in nineteen oh five")
        self.assertEqual(rt.spoken_form("in 1900"), "in nineteen hundred")

    def test_letters_and_tags(self):
        self.assertEqual(rt.spoken_form("C-D-four"), "see dee-four")
        self.assertEqual(rt.spoken_form("[thoughtful] Hmm."), "Hmm.")
        self.assertEqual(rt.spoken_form("CD4"), "see dee four")

    def test_doi(self):
        out = rt.spoken_form("DOI 10.1257/pol.20240806.")
        self.assertIn("one zero dot one two five seven slash p o l dot two zero", out)
        self.assertTrue(out.endswith("zero six."))

    def test_digits_cost_their_airtime(self):
        # The prototype's trick: digits are shorter on the page, not in the ear.
        digits = rt.spoken_chars([{"speaker": "Nadia", "text": "12,779 genes"}])
        words = rt.spoken_chars([{"speaker": "Nadia", "text": "twelve thousand seven hundred seventy-nine genes"}])
        self.assertEqual(digits, words)


class UnspokenForms(unittest.TestCase):
    def test_flags_digits_acronyms_symbols(self):
        found = rt.unspoken_forms("In 22 million CD4 cells, 45% moved; HLA-A2 and α too.")
        for token in ("22", "CD4", "45%", "HLA-A2", "α"):
            self.assertTrue(any(token in f for f in found), (token, found))

    def test_allows_spoken_spellings(self):
        text = ("Welcome to Science TLDR. In twenty-two million C-D-four cells, "
                "forty-five percent moved under Crispr knockdown [thoughtful].")
        self.assertEqual(rt.unspoken_forms(text), [])


class Validate(unittest.TestCase):
    def test_passing_draft(self):
        errors, _ = rt.validate(make_script(), "draft")
        self.assertEqual(errors, [])

    def test_passing_checked(self):
        errors, _ = rt.validate(checked(make_script()), "checked")
        self.assertEqual(errors, [])

    def test_rejects_digits(self):
        s = make_script()
        s["turns"][3]["text"] = "They profiled 12,779 genes. " + s["turns"][3]["text"]
        errors, _ = rt.validate(s, "draft")
        self.assertTrue(any("'12,779'" in e for e in errors), errors)

    def test_too_long(self):
        errors, _ = rt.validate(make_script(target=11_700), "draft")
        self.assertTrue(any("spoken length" in e for e in errors), errors)

    def test_too_short(self):
        s = make_script()
        while rt.spoken_chars(s["turns"]) >= rt.TARGET_MIN_CHARS:
            s["turns"].pop()
        errors, _ = rt.validate(s, "draft")
        self.assertTrue(any("spoken length" in e for e in errors), errors)

    def test_draft_cannot_claim_checked(self):
        errors, _ = rt.validate(checked(make_script()), "draft")
        self.assertTrue(any("checked: false" in e for e in errors), errors)
        self.assertTrue(any("verification_changes" in e for e in errors), errors)

    def test_checked_needs_a_checker_run(self):
        s = checked(make_script())
        s["runs"].pop()
        errors, _ = rt.validate(s, "checked")
        self.assertTrue(any("checker run" in e for e in errors), errors)

    def test_run_record(self):
        s = make_script()
        s["runs"][0]["started"] = "about two o'clock"
        del s["runs"][0]["safeguard_stops"]
        s["paper_source"] = ""
        errors, _ = rt.validate(s, "draft")
        self.assertTrue(any("`started`" in e for e in errors), errors)
        self.assertTrue(any("safeguard_stops" in e for e in errors), errors)
        self.assertTrue(any("paper_source" in e for e in errors), errors)

    def test_api_scripts_skip_provenance(self):
        s = make_script()
        for key in ("runs", "paper_source", "checked"):
            del s[key]
        errors, _ = rt.validate(s)
        self.assertEqual(errors, [])


if __name__ == "__main__":
    unittest.main()


# --- numbers against the paper -------------------------------------------- #

PAPER = (
    "We profiled 22 million cells and recovered 33.4M after filtering. "
    "Of 12,779 genes, 7,807 (67%) had effects. Cross-guide correlation was "
    "0.39 in the discovery cohort. Published 2026."
)


def test_paper_numbers_carry_their_scale_word():
    spoken = rt.paper_spoken_numbers(PAPER)
    assert "twenty two million" in spoken
    assert "thirty three point four million" in spoken
    assert "twelve thousand seven hundred seventy nine" in spoken


def test_leading_zero_of_a_decimal_is_optional():
    # The hosts say "point three nine"; the paper writes 0.39.
    assert not rt.numbers_not_in_paper(
        [{"speaker": "Nadia", "text": "Correlation of point three nine."}], PAPER
    )


def test_figure_absent_from_the_paper_is_flagged():
    assert rt.numbers_not_in_paper(
        [{"speaker": "Nadia", "text": "Correlation of point nine eight."}], PAPER
    ) == ["point nine eight"]


def test_prose_numbers_callbacks_years_and_dois_are_not_flagged():
    turns = [
        {"speaker": "Theo", "text": "Two guides each, and the third act."},
        {"speaker": "Theo", "text": "We covered this in episode seventy-four."},
        {"speaker": "Nadia", "text": "Accepted in twenty twenty-six."},
        {"speaker": "Nadia", "text": "That's D-O-I ten point one zero one six, j dot cell."},
    ]
    assert rt.numbers_not_in_paper(turns, PAPER) == []


def test_a_number_used_for_the_wrong_result_still_passes():
    # The documented limit: presence in the paper, not correct usage.
    assert not rt.numbers_not_in_paper(
        [{"speaker": "Nadia", "text": "Sixty-seven percent of guides worked."}], PAPER
    )
