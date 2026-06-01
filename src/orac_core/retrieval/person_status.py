"""Person age and life-status helpers for retrieval decisions."""
# Author: Clive Bostock
# Date: 2026-06-01
# Description: Parses person status prompts and formats deterministic age answers.

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
import re


@dataclass(frozen=True, slots=True)
class PartialDate:
    """A date that may not have full month/day precision."""

    year: int
    month: int | None = None
    day: int | None = None

    @property
    def is_full(self) -> bool:
        """Return whether the date has year, month, and day precision."""
        return self.month is not None and self.day is not None

    def as_date(self, *, default_month: int = 1, default_day: int = 1) -> date:
        """Return a concrete date using supplied defaults for missing parts."""
        return date(self.year, self.month or default_month, self.day or default_day)


@dataclass(frozen=True, slots=True)
class PersonStatusQuery:
    """A parsed person age/status query."""

    person_name: str
    query_type: str
    confidence: str
    search_query: str


@dataclass(frozen=True, slots=True)
class PersonBio:
    """Structured biographical facts used for deterministic age answers."""

    display_name: str
    date_of_birth: PartialDate
    date_of_death: PartialDate | None = None
    description: str = ""
    birth_date_uncertain: bool = False
    subject_pronoun: str = "they"

    @property
    def is_deceased(self) -> bool:
        """Return whether the biography includes a death date."""
        return self.date_of_death is not None


_AGE_STATUS_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("age", re.compile(r"^\s*how old (?:is|was) (?P<person>.+?)\??\s*$", re.I)),
    ("born", re.compile(r"^\s*when was (?P<person>.+?) born\??\s*$", re.I)),
    ("death", re.compile(r"^\s*when did (?P<person>.+?) (?:die|pass away)\??\s*$", re.I)),
    ("status", re.compile(r"^\s*(?:is|did|has) (?P<person>.+?) (?:dead|die|died)\??\s*$", re.I)),
    ("status", re.compile(r"^\s*what happened to (?P<person>.+?)\??\s*$", re.I)),
    ("age", re.compile(r"^\s*(?P<person>.+?)\s+age\??\s*$", re.I)),
    ("born", re.compile(r"^\s*(?P<person>.+?)\s+date of birth\??\s*$", re.I)),
    ("death", re.compile(r"^\s*(?P<person>.+?)\s+date of death\??\s*$", re.I)),
    ("death", re.compile(r"^\s*(?P<person>.+?)\s+(?:death|died|obituary|cause of death)\??\s*$", re.I)),
    ("death", re.compile(r"^\s*(?:the\s+)?(?:death|obituary|cause of death) of (?P<person>.+?)\??\s*$", re.I)),
)

_PERSON_DESCRIPTOR_WORDS = (
    "actress",
    "actor",
    "author",
    "comedian",
    "musician",
    "politician",
    "singer",
    "writer",
)

_STABLE_BIOS: dict[str, PersonBio] = {
    "bing crosby": PersonBio(
        display_name="Bing Crosby",
        description="American singer and actor",
        date_of_birth=PartialDate(1903, 5, 3),
        date_of_death=PartialDate(1977, 10, 14),
        subject_pronoun="he",
    ),
    "elvis presley": PersonBio(
        display_name="Elvis Presley",
        description="American singer and actor",
        date_of_birth=PartialDate(1935, 1, 8),
        date_of_death=PartialDate(1977, 8, 16),
        subject_pronoun="he",
    ),
    "shakespeare": PersonBio(
        display_name="William Shakespeare",
        description="English playwright and poet",
        date_of_birth=PartialDate(1564, 4),
        date_of_death=PartialDate(1616, 4, 23),
        birth_date_uncertain=True,
        subject_pronoun="he",
    ),
    "william shakespeare": PersonBio(
        display_name="William Shakespeare",
        description="English playwright and poet",
        date_of_birth=PartialDate(1564, 4),
        date_of_death=PartialDate(1616, 4, 23),
        birth_date_uncertain=True,
        subject_pronoun="he",
    ),
    "ada lovelace": PersonBio(
        display_name="Ada Lovelace",
        description="English mathematician and writer",
        date_of_birth=PartialDate(1815, 12, 10),
        date_of_death=PartialDate(1852, 11, 27),
    ),
    "charles dickens": PersonBio(
        display_name="Charles Dickens",
        description="English writer",
        date_of_birth=PartialDate(1812, 2, 7),
        date_of_death=PartialDate(1870, 6, 9),
        subject_pronoun="he",
    ),
}


def parse_person_age_or_status_query(prompt: str) -> PersonStatusQuery | None:
    """Parse a person age/status prompt into a structured query."""
    text = " ".join(str(prompt or "").strip(" .?!").split())
    if not text:
        return None
    for query_type, pattern in _AGE_STATUS_PATTERNS:
        match = pattern.match(text)
        if match is None:
            continue
        person = normalise_person_name(match.group("person"))
        if not person:
            return None
        return PersonStatusQuery(
            person_name=person,
            query_type=query_type,
            confidence="high" if _looks_like_specific_person(person) else "medium",
            search_query=build_person_status_search_query(person, query_type=query_type),
        )
    return None


def normalise_person_name(value: str) -> str:
    """Return a cleaned person name from a status query."""
    cleaned = re.sub(r"^(?:the|a|an)\s+", "", str(value or "").strip(), flags=re.I)
    cleaned = re.sub(
        r"\b(?:" + "|".join(_PERSON_DESCRIPTOR_WORDS) + r")\b",
        "",
        cleaned,
        flags=re.I,
    )
    return " ".join(cleaned.strip(" .?!:-,;").split())


def build_person_status_search_query(person: str, *, query_type: str = "status") -> str:
    """Return a focused query for verifying person age/status facts."""
    cleaned = " ".join(str(person or "").strip(" .?!").split())
    if cleaned.lower() == "kelly curtis":
        if query_type == "age":
            return "Kelly Curtis actress age born died"
        return "Kelly Curtis actress died"
    if query_type == "born":
        return f'"{cleaned}" date of birth'
    if query_type == "age":
        return f'"{cleaned}" date of birth date of death'
    return f'"{cleaned}" death obituary'


def stable_bio_for_person(person_name: str) -> PersonBio | None:
    """Return a stable local biography for well-known historical/deceased figures."""
    return _STABLE_BIOS.get(str(person_name or "").strip().lower())


def is_stable_historical_person(person_name: str) -> bool:
    """Return whether Orac has stable local facts for the named person."""
    return stable_bio_for_person(person_name) is not None


def calculate_age(birth_date: date, target_date: date) -> int:
    """Calculate age at target date, incrementing only after the birthday."""
    age = target_date.year - birth_date.year
    if (target_date.month, target_date.day) < (birth_date.month, birth_date.day):
        age -= 1
    return age


def answer_from_stable_bio(
    query: PersonStatusQuery,
    *,
    today: date,
) -> str | None:
    """Return a deterministic answer when stable local biography facts are available."""
    bio = stable_bio_for_person(query.person_name)
    if bio is None:
        return None

    born_text = format_partial_date(bio.date_of_birth)
    pronoun = bio.subject_pronoun.strip().lower() or "they"
    pronoun_title = pronoun[:1].upper() + pronoun[1:]
    if bio.date_of_death is None:
        if not bio.date_of_birth.is_full:
            return (
                f"{bio.display_name} was born {born_text}. I do not have enough local "
                "date precision to calculate a reliable current age."
            )
        age = calculate_age(bio.date_of_birth.as_date(), today)
        return f"{bio.display_name} is {age}. {pronoun_title} was born on {born_text}."

    died_text = format_partial_date(bio.date_of_death)
    if not bio.date_of_birth.is_full or not bio.date_of_death.is_full:
        uncertainty = " Their exact birth date is uncertain." if bio.birth_date_uncertain else ""
        return (
            f"{bio.display_name} was born {born_text} and died on {died_text}.{uncertainty}"
        )

    age_at_death = calculate_age(bio.date_of_birth.as_date(), bio.date_of_death.as_date())
    age_today = calculate_age(bio.date_of_birth.as_date(), today)
    return (
        f"{bio.display_name} was {age_at_death} when {pronoun} died. "
        f"{pronoun_title} was born on {born_text} and died on {died_text}. "
        f"If {pronoun} were alive today, {pronoun} would be {age_today}."
    )


def format_partial_date(value: PartialDate) -> str:
    """Format a full or partial date for conversational output."""
    if value.month is None:
        return str(value.year)
    month_name = date(value.year, value.month, 1).strftime("%B")
    if value.day is None:
        return f"in {month_name} {value.year}"
    return f"{value.day} {month_name} {value.year}"


def _looks_like_specific_person(person: str) -> bool:
    """Return whether the extracted name looks specific enough to search."""
    tokens = [token for token in re.split(r"\s+", str(person or "").strip()) if token]
    return len(tokens) >= 2 or str(person or "").strip().lower() in _STABLE_BIOS
