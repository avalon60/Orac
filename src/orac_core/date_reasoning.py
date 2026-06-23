"""Deterministic date and birth-order reasoning helpers."""
# Author: Clive Bostock
# Date: 02-Jun-2026
# Description: Parses dates and resolves birth-date comparisons without LLM reasoning.

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any
import re


class DateReasoningError(ValueError):
    """Raised when a date or date-reasoning request cannot be resolved safely."""


@dataclass(frozen=True, slots=True)
class GroupMemberBirthDate:
    """Birth-date facts for a known group member."""

    name: str
    birth_date: date
    is_surviving: bool = True
    is_original_member: bool = True


@dataclass(frozen=True, slots=True)
class DateReasoningAnswer:
    """A deterministic answer generated from normalised birth dates."""

    answer: str
    reason_code: str
    assumptions: tuple[str, ...] = ()
    people: dict[str, date] | None = None


_MONTHS: dict[str, int] = {
    "january": 1,
    "jan": 1,
    "february": 2,
    "feb": 2,
    "march": 3,
    "mar": 3,
    "april": 4,
    "apr": 4,
    "may": 5,
    "june": 6,
    "jun": 6,
    "july": 7,
    "jul": 7,
    "august": 8,
    "aug": 8,
    "september": 9,
    "sep": 9,
    "sept": 9,
    "october": 10,
    "oct": 10,
    "november": 11,
    "nov": 11,
    "december": 12,
    "dec": 12,
}

_ISO_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_DAY_MONTH_YEAR_RE = re.compile(
    r"^(?P<day>\d{1,2})(?:st|nd|rd|th)?\s+"
    r"(?P<month>[A-Za-z]+)\s+"
    r"(?P<year>\d{4})$",
    re.I,
)
_MONTH_DAY_YEAR_RE = re.compile(
    r"^(?P<month>[A-Za-z]+)\s+"
    r"(?P<day>\d{1,2})(?:st|nd|rd|th)?(?:,)?\s+"
    r"(?P<year>\d{4})$",
    re.I,
)

_QUEEN_CLASSIC_LINEUP: tuple[GroupMemberBirthDate, ...] = (
    GroupMemberBirthDate(
        name="Freddie Mercury",
        birth_date=date(1946, 9, 5),
        is_surviving=False,
    ),
    GroupMemberBirthDate(name="Brian May", birth_date=date(1947, 7, 19)),
    GroupMemberBirthDate(name="Roger Taylor", birth_date=date(1949, 7, 26)),
    GroupMemberBirthDate(name="John Deacon", birth_date=date(1951, 8, 19)),
)

_KNOWN_PERSON_BIRTH_DATES: dict[str, date] = {
    member.name: member.birth_date for member in _QUEEN_CLASSIC_LINEUP
}
_PERSON_ALIASES: dict[str, str] = {
    "freddie": "Freddie Mercury",
    "freddie mercury": "Freddie Mercury",
    "brian": "Brian May",
    "brian may": "Brian May",
    "roger": "Roger Taylor",
    "roger taylor": "Roger Taylor",
    "john": "John Deacon",
    "john deacon": "John Deacon",
}

_DATE_REASONING_TERMS: tuple[str, ...] = (
    "oldest",
    "youngest",
    "older than",
    "younger than",
    "born before",
    "born after",
    "age order",
    "born first",
)
_CHALLENGE_TERMS: tuple[str, ...] = (
    "surely",
    "are you sure",
    "that can't be right",
    "that cannot be right",
    "you are wrong",
    "you're wrong",
    "isn't",
    "wasn't",
)


def parse_human_date(date_text: str) -> date:
    """Parse a common human-readable date into ``datetime.date``.

    Args:
        date_text: Date text such as ``5 September 1946`` or ``1946-09-05``.

    Returns:
        A normalised ``datetime.date``.

    Raises:
        DateReasoningError: If the date is malformed, ambiguous, or unsupported.
    """
    text = " ".join(str(date_text or "").strip().split())
    if not text:
        raise DateReasoningError("Date text is empty.")
    if _ISO_DATE_RE.match(text):
        try:
            return date.fromisoformat(text)
        except ValueError as exc:
            raise DateReasoningError(f"Invalid ISO date: {date_text}") from exc
    if re.search(r"\d{1,2}[/-]\d{1,2}[/-]\d{2,4}", text):
        raise DateReasoningError(
            f"Ambiguous numeric date is not supported: {date_text}"
        )

    for pattern in (_DAY_MONTH_YEAR_RE, _MONTH_DAY_YEAR_RE):
        match = pattern.match(text)
        if match is None:
            continue
        month = _MONTHS.get(match.group("month").lower())
        if month is None:
            raise DateReasoningError(f"Unknown month in date: {date_text}")
        try:
            return date(
                int(match.group("year")),
                month,
                int(match.group("day")),
            )
        except ValueError as exc:
            raise DateReasoningError(f"Invalid date: {date_text}") from exc

    raise DateReasoningError(f"Unsupported date format: {date_text}")


def sort_people_by_birth_date(people: dict[str, date]) -> list[tuple[str, date]]:
    """Return people sorted from oldest to youngest by birth date."""
    _validate_people(people)
    return sorted(people.items(), key=lambda item: (item[1], item[0].lower()))


def get_oldest_person(people: dict[str, date]) -> tuple[str, date]:
    """Return the person with the earliest birth date."""
    return sort_people_by_birth_date(people)[0]


def get_youngest_person(people: dict[str, date]) -> tuple[str, date]:
    """Return the person with the latest birth date."""
    return sort_people_by_birth_date(people)[-1]


def compare_birth_dates(
    person_a: str,
    date_a: date,
    person_b: str,
    date_b: date,
) -> dict[str, Any]:
    """Compare two birth dates using earliest-date-means-oldest semantics."""
    if not person_a or not person_b:
        raise DateReasoningError("Both person names are required.")
    if not isinstance(date_a, date) or not isinstance(date_b, date):
        raise DateReasoningError("Both birth dates must be datetime.date values.")

    if date_a < date_b:
        older_person = person_a
        older_date = date_a
        younger_person = person_b
        younger_date = date_b
        relation = "a_is_older"
    elif date_b < date_a:
        older_person = person_b
        older_date = date_b
        younger_person = person_a
        younger_date = date_a
        relation = "b_is_older"
    else:
        older_person = None
        older_date = date_a
        younger_person = None
        younger_date = date_b
        relation = "same_birth_date"

    return {
        "person_a": person_a,
        "date_a": date_a,
        "person_b": person_b,
        "date_b": date_b,
        "relation": relation,
        "older_person": older_person,
        "older_birth_date": older_date,
        "younger_person": younger_person,
        "younger_birth_date": younger_date,
        "earlier_birth_date": min(date_a, date_b),
        "later_birth_date": max(date_a, date_b),
        "born_before_means_older": True,
        "born_after_means_younger": True,
    }


def answer_date_reasoning_query(prompt: str) -> DateReasoningAnswer | None:
    """Return a deterministic date-reasoning answer for supported prompts."""
    normalized = _normalise_prompt(prompt)
    if not normalized or not _looks_like_date_reasoning_prompt(normalized):
        return None

    comparison = _answer_known_person_comparison(normalized)
    if comparison is not None:
        return comparison

    if "queen" in normalized:
        return _answer_queen_group_query(normalized)

    if _mentions_group_age_order(normalized):
        return DateReasoningAnswer(
            answer=(
                "I need confirmed group membership and birth dates before I can "
                "answer that age-order question deterministically. Which scope "
                "should I use, and should I search for the members' birth dates?"
            ),
            reason_code="missing_group_birth_dates",
        )
    return None


def _answer_known_person_comparison(prompt: str) -> DateReasoningAnswer | None:
    """Return a deterministic answer when two known people are mentioned."""
    mentioned = _mentioned_known_people(prompt)
    if len(mentioned) < 2:
        return None
    person_a, person_b = mentioned[0], mentioned[1]
    date_a = _KNOWN_PERSON_BIRTH_DATES[person_a]
    date_b = _KNOWN_PERSON_BIRTH_DATES[person_b]
    comparison = compare_birth_dates(person_a, date_a, person_b, date_b)
    older = str(comparison["older_person"])
    younger = str(comparison["younger_person"])
    older_date = comparison["older_birth_date"]
    younger_date = comparison["younger_birth_date"]
    challenge_prefix = "You are right. " if _is_challenge(prompt) else ""

    if "born after" in prompt:
        relation_sentence = (
            f"Since {younger} was born later, {younger} was younger than {older}."
        )
    else:
        relation_sentence = (
            f"Since {older} was born earlier, {older} was older than {younger}."
        )
    return DateReasoningAnswer(
        answer=(
            f"{challenge_prefix}{older} was born on {_format_date(older_date)} "
            f"and {younger} was born on {_format_date(younger_date)}. "
            f"{relation_sentence}"
        ),
        reason_code="known_birth_date_comparison",
        people={person_a: date_a, person_b: date_b},
    )


def _answer_queen_group_query(prompt: str) -> DateReasoningAnswer:
    """Return a deterministic answer for supported Queen line-up questions."""
    members = list(_QUEEN_CLASSIC_LINEUP)
    assumptions = ["Queen's classic line-up"]
    scope_label = "Queen's classic line-up"
    if "surviving" in prompt:
        members = [member for member in members if member.is_surviving]
        assumptions = ["Queen's surviving original members"]
        scope_label = "Queen's surviving original members"
    elif "original" in prompt:
        members = [member for member in members if member.is_original_member]
        assumptions = ["Queen's original members as represented by the classic line-up"]
        scope_label = "Queen's original members"

    people = {member.name: member.birth_date for member in members}
    ordered = sort_people_by_birth_date(people)

    if "age order" in prompt:
        order = "; ".join(
            f"{index}. {name} ({_format_date(birth_date)})"
            for index, (name, birth_date) in enumerate(ordered, start=1)
        )
        return DateReasoningAnswer(
            answer=f"For {scope_label}, oldest to youngest: {order}.",
            reason_code="known_group_age_order",
            assumptions=tuple(assumptions),
            people=people,
        )

    if "youngest" in prompt:
        person, birth_date = get_youngest_person(people)
        return DateReasoningAnswer(
            answer=(
                f"For {scope_label}, {person} was the youngest member. "
                f"{person} was born on {_format_date(birth_date)}."
            ),
            reason_code="known_group_youngest",
            assumptions=tuple(assumptions),
            people=people,
        )

    person, birth_date = get_oldest_person(people)
    if "surviving" in prompt and person == "Brian May":
        answer = (
            "For Queen's surviving original members, Brian May is the oldest. "
            "Freddie Mercury is excluded because he is deceased. "
            "Brian May was born on 19 July 1947, before Roger Taylor "
            "(26 July 1949) and John Deacon (19 August 1951)."
        )
    else:
        answer = (
            f"For {scope_label}, {person} was the oldest member. "
            f"{person} was born on {_format_date(birth_date)}, the earliest "
            "birth date in that line-up."
        )
    return DateReasoningAnswer(
        answer=answer,
        reason_code="known_group_oldest",
        assumptions=tuple(assumptions),
        people=people,
    )


def _validate_people(people: dict[str, date]) -> None:
    """Validate a person-to-birth-date mapping."""
    if not people:
        raise DateReasoningError("At least one person and birth date is required.")
    for person, birth_date in people.items():
        if not str(person or "").strip():
            raise DateReasoningError("Person names must be non-empty.")
        if not isinstance(birth_date, date):
            raise DateReasoningError(f"Birth date for {person!r} is not a date.")


def _looks_like_date_reasoning_prompt(prompt: str) -> bool:
    """Return whether prompt asks for date or age-order reasoning."""
    return any(term in prompt for term in _DATE_REASONING_TERMS) or (
        "member" in prompt and ("older" in prompt or "younger" in prompt)
    )


def _mentions_group_age_order(prompt: str) -> bool:
    """Return whether a prompt asks for age-order reasoning about a group."""
    return bool(
        re.search(
            r"\b(?:band|team|group|line[- ]?up|member|members)\b",
            prompt,
            re.I,
        )
    )


def _mentioned_known_people(prompt: str) -> list[str]:
    """Return known people mentioned in prompt, preserving first mention order."""
    matches: list[tuple[int, str]] = []
    for alias, canonical in _PERSON_ALIASES.items():
        match = re.search(rf"\b{re.escape(alias)}\b", prompt, re.I)
        if match is not None:
            matches.append((match.start(), canonical))
    ordered: list[str] = []
    for _, canonical in sorted(matches, key=lambda item: item[0]):
        if canonical not in ordered:
            ordered.append(canonical)
    return ordered


def _is_challenge(prompt: str) -> bool:
    """Return whether the user appears to be challenging a prior conclusion."""
    return any(term in prompt for term in _CHALLENGE_TERMS)


def _normalise_prompt(prompt: str) -> str:
    """Return a lower-case prompt with compact whitespace."""
    return " ".join(str(prompt or "").lower().strip().split())


def _format_date(value: date) -> str:
    """Format a date for conversational output."""
    return f"{value.day} {value.strftime('%B')} {value.year}"
