"""Tests for deterministic date and birth-order reasoning."""
# Author: Clive Bostock
# Date: 02-Jun-2026
# Description: Verifies date parsing, birth-date sorting, and Queen age-order answers.

from __future__ import annotations

from datetime import date
from pathlib import Path
import sys
import unittest


PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))


from orac_core import DateReasoningError
from orac_core import answer_date_reasoning_query
from orac_core import compare_birth_dates
from orac_core import get_oldest_person
from orac_core import get_youngest_person
from orac_core import parse_human_date
from orac_core import sort_people_by_birth_date


class DateReasoningUtilityTests(unittest.TestCase):
    """Tests deterministic date parsing and birth-date comparisons."""

    def test_parse_human_date_accepts_common_formats(self) -> None:
        """Common date formats are normalised to ``datetime.date``."""
        self.assertEqual(parse_human_date("5 September 1946"), date(1946, 9, 5))
        self.assertEqual(parse_human_date("19 July 1947"), date(1947, 7, 19))
        self.assertEqual(parse_human_date("1946-09-05"), date(1946, 9, 5))

    def test_freddie_mercury_is_older_than_brian_may(self) -> None:
        """Earlier birth date means older for Freddie Mercury and Brian May."""
        comparison = compare_birth_dates(
            "Freddie Mercury",
            parse_human_date("5 September 1946"),
            "Brian May",
            parse_human_date("19 July 1947"),
        )

        self.assertEqual(comparison["older_person"], "Freddie Mercury")
        self.assertEqual(comparison["younger_person"], "Brian May")
        self.assertEqual(comparison["relation"], "a_is_older")

    def test_queen_classic_lineup_sorts_oldest_to_youngest(self) -> None:
        """Queen's classic line-up is sorted by earliest birth date first."""
        people = {
            "Freddie Mercury": parse_human_date("5 September 1946"),
            "Brian May": parse_human_date("19 July 1947"),
            "Roger Taylor": parse_human_date("26 July 1949"),
            "John Deacon": parse_human_date("19 August 1951"),
        }

        ordered = sort_people_by_birth_date(people)

        self.assertEqual(
            [name for name, _ in ordered],
            ["Freddie Mercury", "Brian May", "Roger Taylor", "John Deacon"],
        )
        self.assertEqual(get_oldest_person(people)[0], "Freddie Mercury")
        self.assertEqual(get_youngest_person(people)[0], "John Deacon")

    def test_born_before_maps_to_older(self) -> None:
        """A person born before another person is older."""
        comparison = compare_birth_dates(
            "Freddie Mercury",
            date(1946, 9, 5),
            "Brian May",
            date(1947, 7, 19),
        )

        self.assertTrue(comparison["born_before_means_older"])
        self.assertEqual(comparison["older_person"], "Freddie Mercury")

    def test_born_after_maps_to_younger(self) -> None:
        """A person born after another person is younger."""
        comparison = compare_birth_dates(
            "Brian May",
            date(1947, 7, 19),
            "Freddie Mercury",
            date(1946, 9, 5),
        )

        self.assertTrue(comparison["born_after_means_younger"])
        self.assertEqual(comparison["younger_person"], "Brian May")

    def test_malformed_and_ambiguous_dates_raise(self) -> None:
        """Malformed and ambiguous dates are rejected rather than guessed."""
        for value in ("September 1946", "05/09/1946", "1946-13-05", "nonsense"):
            with self.subTest(value=value):
                with self.assertRaises(DateReasoningError):
                    parse_human_date(value)


class DateReasoningAnswerTests(unittest.TestCase):
    """Tests deterministic answer generation for supported prompts."""

    def test_correction_challenge_re_evaluates_birth_order(self) -> None:
        """A correction prompt uses deterministic earlier-date-is-older logic."""
        answer = answer_date_reasoning_query(
            "surely Freddie Mercury was the oldest if he was born before Brian May"
        )

        self.assertIsNotNone(answer)
        assert answer is not None
        self.assertIn("You are right.", answer.answer)
        self.assertIn("Freddie Mercury was born on 5 September 1946", answer.answer)
        self.assertIn("Brian May was born on 19 July 1947", answer.answer)
        self.assertIn("Freddie Mercury was older than Brian May", answer.answer)

    def test_oldest_member_of_queen_defaults_to_classic_lineup(self) -> None:
        """Queen oldest-member question uses the classic-line-up assumption."""
        answer = answer_date_reasoning_query(
            "Who was the oldest member of the band Queen?"
        )

        self.assertIsNotNone(answer)
        assert answer is not None
        self.assertIn(
            "For Queen's classic line-up, Freddie Mercury was the oldest member.",
            answer.answer,
        )
        self.assertEqual(answer.assumptions, ("Queen's classic line-up",))

    def test_oldest_surviving_original_member_of_queen(self) -> None:
        """Surviving original-member scope excludes Freddie Mercury."""
        answer = answer_date_reasoning_query(
            "Who is the oldest surviving original member of Queen?"
        )

        self.assertIsNotNone(answer)
        assert answer is not None
        self.assertIn("Brian May is the oldest", answer.answer)
        self.assertIn(
            "Freddie Mercury is excluded because he is deceased",
            answer.answer,
        )
        self.assertIn("Brian May was born on 19 July 1947", answer.answer)

    def test_unknown_group_age_order_does_not_guess(self) -> None:
        """Unknown group membership is reported as missing deterministic input."""
        answer = answer_date_reasoning_query(
            "Who was the oldest member of The Example Band?"
        )

        self.assertIsNotNone(answer)
        assert answer is not None
        self.assertIn("confirmed group membership and birth dates", answer.answer)
        self.assertEqual(answer.reason_code, "missing_group_birth_dates")


if __name__ == "__main__":
    unittest.main()
