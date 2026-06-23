"""Deterministic read-only Home Assistant sensor query support."""
# Author: Clive Bostock
# Date: 12-Jun-2026
# Description: Resolves and renders temperature, humidity, availability, and freshness queries.

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
import json
import re
from typing import Any, Iterable, Mapping


DEFAULT_STALE_HOURS = 6.0
HUMIDITY_DRY_BELOW = 40.0
HUMIDITY_COMFORTABLE_MAX = 60.0
HUMIDITY_HUMID_MAX = 70.0
TEMPERATURE_COLD_BELOW_C = 16.0
TEMPERATURE_COOL_BELOW_C = 18.0
TEMPERATURE_SLIGHTLY_COOL_BELOW_C = 19.0
TEMPERATURE_COMFORTABLE_BELOW_C = 23.0
TEMPERATURE_WARM_MAX_C = 26.0
SENSOR_ROLES = frozenset({"temperature", "humidity", "battery", "unknown"})
UNAVAILABLE_STATES = frozenset({"", "none", "unavailable", "unknown"})


class HomeAssistantSensorQueryError(ValueError):
    """Raised when a sensor query cannot be resolved deterministically."""

    def __init__(self, code: str, message: str) -> None:
        """Initialise a structured read-only sensor-query failure."""
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class SensorQueryRequest:
    """Parsed deterministic Home Assistant sensor query."""

    intent: str
    areas: tuple[str, ...] = ()
    sensor_role: str | None = None


@dataclass(frozen=True)
class SensorReading:
    """One classified Home Assistant sensor reading."""

    entity_id: str
    name: str
    area_name: str
    role: str
    state: str
    numeric_value: float | None
    unit: str | None
    last_updated: datetime | None

    @property
    def available(self) -> bool:
        """Return whether the sensor has an available state value."""
        return self.state.strip().lower() not in UNAVAILABLE_STATES


@dataclass(frozen=True)
class SensorQueryResult:
    """Rendered sensor-query result and supporting provenance fields."""

    content: str
    entity_ids: tuple[str, ...]
    areas: tuple[str, ...]
    status: str = "complete"


class AreaResolver:
    """Resolve exact Home Assistant area names and aliases."""

    def resolve(
        self,
        reference: str,
        rows: Iterable[Mapping[str, Any]],
    ) -> str:
        """Return one canonical area name for an exact name or alias."""
        target = _normalise(reference)
        matches = {
            row["area_name"]
            for row in rows
            if row["area_name"]
            and target in {row["area_name"], *row["area_aliases"]}
        }
        if not matches:
            raise HomeAssistantSensorQueryError(
                "unknown_area",
                f"Home Assistant area '{reference}' was not found.",
            )
        if len(matches) > 1:
            raise HomeAssistantSensorQueryError(
                "ambiguous_area",
                f"Home Assistant area '{reference}' is ambiguous.",
            )
        return next(iter(matches))


def parse_sensor_query(prompt: str) -> SensorQueryRequest | None:
    """Parse a supported read-only temperature or humidity query."""
    command = _normalise_prompt(prompt)

    if re.fullmatch(r"are (?:any )?sensors unavailable", command):
        return SensorQueryRequest(intent="sensor_availability")

    match = re.fullmatch(
        r"when was (?:the )?(.+?)(?: (temperature|humidity))? sensor last updated",
        command,
    )
    if match:
        return SensorQueryRequest(
            intent="sensor_freshness",
            areas=(_normalise(match.group(1)),),
            sensor_role=match.group(2),
        )

    match = re.fullmatch(
        r"which is warmer,? (?:the )?(.+?) or (?:the )?(.+)",
        command,
    )
    if match:
        return SensorQueryRequest(
            intent="compare_area_temperature",
            areas=(_normalise(match.group(1)), _normalise(match.group(2))),
            sensor_role="temperature",
        )

    match = re.fullmatch(
        r"(?:what is|what's) (?:the )?temperature (?:in|on) (?:the )?(.+)",
        command,
    )
    if match:
        return SensorQueryRequest(
            intent="area_temperature",
            areas=(_normalise(match.group(1)),),
            sensor_role="temperature",
        )

    match = re.fullmatch(
        r"(?:what is|what's) (?:the )?(.+?) temperature",
        command,
    )
    if match:
        return SensorQueryRequest(
            intent="area_temperature",
            areas=(_normalise(match.group(1)),),
            sensor_role="temperature",
        )

    match = re.fullmatch(
        r"(?:what is|what's) (?:the )?humidity (?:in|on) (?:the )?(.+)",
        command,
    )
    if match:
        return SensorQueryRequest(
            intent="area_humidity",
            areas=(_normalise(match.group(1)),),
            sensor_role="humidity",
        )

    match = re.fullmatch(
        r"(?:what is|what's) (?:the )?(.+?) humidity",
        command,
    )
    if match:
        return SensorQueryRequest(
            intent="area_humidity",
            areas=(_normalise(match.group(1)),),
            sensor_role="humidity",
        )

    match = re.fullmatch(r"how humid is (?:the )?(.+)", command)
    if match:
        return SensorQueryRequest(
            intent="area_humidity",
            areas=(_normalise(match.group(1)),),
            sensor_role="humidity",
        )

    match = re.fullmatch(r"is (?:the )?(.+?) humid", command)
    if match:
        return SensorQueryRequest(
            intent="area_humidity",
            areas=(_normalise(match.group(1)),),
            sensor_role="humidity",
        )

    match = re.fullmatch(
        r"(?:what is|what's) (?:the )?(?:temperature and humidity|climate) "
        r"(?:in|on) (?:the )?(.+)",
        command,
    )
    if match:
        return SensorQueryRequest(
            intent="area_climate_summary",
            areas=(_normalise(match.group(1)),),
        )

    return None


def execute_sensor_query(
    request: SensorQueryRequest,
    source_rows: Iterable[Mapping[str, Any]],
    *,
    now: datetime | None = None,
    stale_after: timedelta = timedelta(hours=DEFAULT_STALE_HOURS),
    area_resolver: AreaResolver | None = None,
) -> SensorQueryResult:
    """Resolve and render one deterministic read-only sensor query."""
    rows = _normalise_rows(source_rows)
    current_time = (now or datetime.now(UTC)).astimezone(UTC)
    resolver = area_resolver or AreaResolver()

    if request.intent == "sensor_availability":
        return _availability_result(rows)

    canonical_areas = tuple(resolver.resolve(area, rows) for area in request.areas)
    if request.intent == "compare_area_temperature":
        readings = tuple(
            _one_area_reading(rows, area, "temperature") for area in canonical_areas
        )
        return _comparison_result(readings, current_time, stale_after)
    if request.intent == "sensor_freshness":
        return _freshness_result(
            rows,
            canonical_areas[0],
            request.sensor_role,
            current_time,
            stale_after,
        )
    if request.intent == "area_climate_summary":
        temperature = _one_area_reading(rows, canonical_areas[0], "temperature")
        humidity = _one_area_reading(rows, canonical_areas[0], "humidity")
        return _climate_summary_result(
            temperature,
            humidity,
            current_time,
            stale_after,
        )
    if request.sensor_role in {"temperature", "humidity"}:
        reading = _one_area_reading(
            rows,
            canonical_areas[0],
            request.sensor_role,
        )
        return _single_reading_result(reading, current_time, stale_after)
    raise HomeAssistantSensorQueryError(
        "unsupported_query",
        "That Home Assistant sensor query is not supported.",
    )


def resolve_sensor_query_entity_ids(
    request: SensorQueryRequest,
    source_rows: Iterable[Mapping[str, Any]],
    *,
    area_resolver: AreaResolver | None = None,
) -> tuple[str, ...]:
    """Resolve the sensor entity IDs required by one deterministic query."""
    rows = _normalise_rows(source_rows)
    resolver = area_resolver or AreaResolver()
    if request.intent == "sensor_availability":
        return tuple(
            sorted(
                row["entity_id"]
                for row in rows
                if row["domain"] == "sensor" and not row["disabled_by"]
            )
        )

    canonical_areas = tuple(resolver.resolve(area, rows) for area in request.areas)
    if request.intent == "compare_area_temperature":
        return tuple(
            _one_area_reading(rows, area, "temperature").entity_id
            for area in canonical_areas
        )
    if request.intent == "area_climate_summary":
        area = canonical_areas[0]
        return (
            _one_area_reading(rows, area, "temperature").entity_id,
            _one_area_reading(rows, area, "humidity").entity_id,
        )
    if request.intent == "sensor_freshness":
        roles = {request.sensor_role} if request.sensor_role else {"temperature", "humidity"}
        entity_ids = tuple(
            sorted(
                row["entity_id"]
                for row in rows
                if row["area_name"] == canonical_areas[0]
                and row["domain"] == "sensor"
                and not row["disabled_by"]
                and classify_sensor_role(row) in roles
            )
        )
        if not entity_ids:
            label = request.sensor_role or "temperature or humidity"
            raise HomeAssistantSensorQueryError(
                "sensor_not_found",
                f"I don't have a known {label} sensor for {canonical_areas[0]}.",
            )
        return entity_ids
    if request.sensor_role in {"temperature", "humidity"}:
        return (
            _one_area_reading(
                rows,
                canonical_areas[0],
                request.sensor_role,
            ).entity_id,
        )
    raise HomeAssistantSensorQueryError(
        "unsupported_query",
        "That Home Assistant sensor query is not supported.",
    )


def classify_sensor_role(row: Mapping[str, Any]) -> str:
    """Classify a sensor using Home Assistant metadata and conservative fallback."""
    device_class = _normalise(row.get("device_class"))
    if device_class in {"temperature", "humidity", "battery"}:
        return device_class

    unit = _normalise_unit(row.get("unit_of_measurement"))
    identifying_text = " ".join(
        _normalise(row.get(key))
        for key in (
            "entity_id",
            "object_id",
            "entity_name",
            "original_name",
            "friendly_name",
        )
    ).replace("_", " ").replace(".", " ")
    if unit in {"°c", "c", "°f", "f"}:
        return "temperature"
    if re.search(r"\btemperature\b", identifying_text):
        return "temperature"
    if re.search(r"\bhumidity\b", identifying_text):
        return "humidity"
    if re.search(r"\bbattery\b", identifying_text):
        return "battery"
    return "unknown"


def interpret_humidity(value: float) -> str:
    """Return the default qualitative humidity interpretation."""
    if value < HUMIDITY_DRY_BELOW:
        return "dry"
    if value <= HUMIDITY_COMFORTABLE_MAX:
        return "comfortable"
    if value <= HUMIDITY_HUMID_MAX:
        return "humid"
    return "very humid with a possible damp concern"


def interpret_temperature(value_c: float) -> str:
    """Return the default qualitative Celsius temperature interpretation."""
    if value_c < TEMPERATURE_COLD_BELOW_C:
        return "cold"
    if value_c < TEMPERATURE_COOL_BELOW_C:
        return "cool"
    if value_c < TEMPERATURE_SLIGHTLY_COOL_BELOW_C:
        return "slightly cool"
    if value_c < TEMPERATURE_COMFORTABLE_BELOW_C:
        return "comfortable"
    if value_c <= TEMPERATURE_WARM_MAX_C:
        return "warm"
    return "hot"


def _one_area_reading(
    rows: list[dict[str, Any]],
    area_name: str,
    role: str,
) -> SensorReading:
    """Return exactly one active sensor reading for an area and role."""
    matches = [
        _reading(row)
        for row in rows
        if row["area_name"] == area_name
        and row["domain"] == "sensor"
        and not row["disabled_by"]
        and classify_sensor_role(row) == role
    ]
    if not matches:
        raise HomeAssistantSensorQueryError(
            "sensor_not_found",
            f"I don't have a known {role} sensor for {area_name}.",
        )
    if len(matches) > 1:
        raise HomeAssistantSensorQueryError(
            "ambiguous_sensor",
            f"I found more than one {role} sensor for {area_name}, "
            "so a preferred sensor needs to be configured.",
        )
    return matches[0]


def _single_reading_result(
    reading: SensorReading,
    now: datetime,
    stale_after: timedelta,
) -> SensorQueryResult:
    """Render one temperature or humidity reading."""
    area = reading.area_name.title()
    if not reading.available or reading.numeric_value is None:
        return SensorQueryResult(
            content=f"The {area} {reading.role} sensor is unavailable.",
            entity_ids=(reading.entity_id,),
            areas=(reading.area_name,),
            status="unavailable",
        )
    value_text = _value_text(reading)
    interpretation = (
        interpret_temperature(_temperature_c(reading))
        if reading.role == "temperature"
        else interpret_humidity(reading.numeric_value)
    )
    freshness = _freshness_clause(reading.last_updated, now, stale_after)
    return SensorQueryResult(
        content=(
            f"The {area} {reading.role} is {value_text}. "
            f"That is {interpretation}.{freshness}"
        ),
        entity_ids=(reading.entity_id,),
        areas=(reading.area_name,),
    )


def _climate_summary_result(
    temperature: SensorReading,
    humidity: SensorReading,
    now: datetime,
    stale_after: timedelta,
) -> SensorQueryResult:
    """Render temperature and humidity for one area."""
    if not temperature.available or temperature.numeric_value is None:
        return _single_reading_result(temperature, now, stale_after)
    if not humidity.available or humidity.numeric_value is None:
        return _single_reading_result(humidity, now, stale_after)
    area = temperature.area_name.title()
    stale = any(
        _is_stale(reading.last_updated, now, stale_after)
        for reading in (temperature, humidity)
    )
    stale_text = " One or more readings may be stale." if stale else ""
    return SensorQueryResult(
        content=(
            f"The {area} is {_value_text(temperature)} with humidity at "
            f"{_value_text(humidity)}. The temperature is "
            f"{interpret_temperature(_temperature_c(temperature))} and the humidity "
            f"is {interpret_humidity(humidity.numeric_value)}.{stale_text}"
        ),
        entity_ids=(temperature.entity_id, humidity.entity_id),
        areas=(temperature.area_name,),
    )


def _comparison_result(
    readings: tuple[SensorReading, SensorReading],
    now: datetime,
    stale_after: timedelta,
) -> SensorQueryResult:
    """Render a comparison between two area temperature readings."""
    first, second = readings
    for reading in readings:
        if not reading.available or reading.numeric_value is None:
            return _single_reading_result(reading, now, stale_after)
    first_c = _temperature_c(first)
    second_c = _temperature_c(second)
    if abs(first_c - second_c) < 0.05:
        comparison = "They are the same temperature"
    else:
        warmer = first if first_c > second_c else second
        difference = abs(first_c - second_c)
        comparison = f"{warmer.area_name.title()} is warmer by {difference:.1f}°C"
    stale_text = (
        " One or both readings may be stale."
        if any(_is_stale(item.last_updated, now, stale_after) for item in readings)
        else ""
    )
    return SensorQueryResult(
        content=(
            f"{comparison}. {first.area_name.title()} is {_value_text(first)} and "
            f"{second.area_name.title()} is {_value_text(second)}.{stale_text}"
        ),
        entity_ids=(first.entity_id, second.entity_id),
        areas=(first.area_name, second.area_name),
    )


def _availability_result(rows: list[dict[str, Any]]) -> SensorQueryResult:
    """Render unavailable Home Assistant sensor entities."""
    unavailable = [
        _reading(row)
        for row in rows
        if row["domain"] == "sensor"
        and not row["disabled_by"]
        and _normalise(row["current_state"]) in UNAVAILABLE_STATES
    ]
    if not unavailable:
        return SensorQueryResult(
            content="No active Home Assistant sensors are unavailable.",
            entity_ids=(),
            areas=(),
        )
    names = ", ".join(sorted({reading.name.title() for reading in unavailable}))
    return SensorQueryResult(
        content=f"Unavailable Home Assistant sensors: {names}.",
        entity_ids=tuple(sorted(reading.entity_id for reading in unavailable)),
        areas=tuple(sorted({reading.area_name for reading in unavailable if reading.area_name})),
        status="unavailable",
    )


def _freshness_result(
    rows: list[dict[str, Any]],
    area_name: str,
    role: str | None,
    now: datetime,
    stale_after: timedelta,
) -> SensorQueryResult:
    """Render conservative freshness for climate sensors in one area."""
    roles = {role} if role else {"temperature", "humidity"}
    readings = [
        _reading(row)
        for row in rows
        if row["area_name"] == area_name
        and row["domain"] == "sensor"
        and not row["disabled_by"]
        and classify_sensor_role(row) in roles
    ]
    if not readings:
        label = role or "temperature or humidity"
        raise HomeAssistantSensorQueryError(
            "sensor_not_found",
            f"I don't have a known {label} sensor for {area_name}.",
        )
    timestamps = [reading.last_updated for reading in readings if reading.last_updated]
    if not timestamps:
        content = f"The {area_name.title()} sensor has no known update time."
    else:
        oldest = min(timestamps)
        age = now - oldest.astimezone(UTC)
        content = (
            f"The {area_name.title()} sensor last updated {_age_text(age)} ago."
        )
        if age > stale_after:
            content += " The reading may be stale."
    return SensorQueryResult(
        content=content,
        entity_ids=tuple(sorted(reading.entity_id for reading in readings)),
        areas=(area_name,),
    )


def _normalise_rows(rows: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Return resolution rows with normalised identifiers and metadata."""
    normalised: dict[str, dict[str, Any]] = {}
    for source in rows:
        row = {str(key).lower(): value for key, value in source.items()}
        entity_id = _normalise(row.get("entity_id"))
        if "." not in entity_id:
            continue
        domain, object_id = entity_id.split(".", 1)
        normalised.setdefault(
            entity_id,
            {
                "entity_id": entity_id,
                "domain": _normalise(row.get("domain")) or domain,
                "object_id": _normalise(row.get("object_id")) or object_id,
                "entity_name": _normalise(row.get("entity_name")),
                "original_name": _normalise(row.get("original_name")),
                "friendly_name": _normalise(row.get("friendly_name")),
                "device_name": _normalise(row.get("device_name")),
                "area_name": _normalise(row.get("area_name")),
                "area_aliases": _json_names(row.get("area_aliases")),
                "current_state": str(row.get("current_state") or "").strip(),
                "device_class": _normalise(row.get("device_class")),
                "unit_of_measurement": str(
                    row.get("unit_of_measurement") or ""
                ).strip(),
                "last_changed": _timestamp(row.get("last_changed")),
                "last_updated": _timestamp(row.get("last_updated")),
                "disabled_by": _normalise(row.get("disabled_by")),
            }
        )
    return list(normalised.values())


def _reading(row: Mapping[str, Any]) -> SensorReading:
    """Build a typed sensor reading from one normalised resolution row."""
    state = str(row.get("current_state") or "").strip()
    try:
        numeric_value = float(state)
    except (TypeError, ValueError):
        numeric_value = None
    name = (
        row.get("friendly_name")
        or row.get("entity_name")
        or row.get("device_name")
        or str(row.get("object_id") or "sensor").replace("_", " ")
    )
    return SensorReading(
        entity_id=str(row["entity_id"]),
        name=str(name),
        area_name=str(row.get("area_name") or ""),
        role=classify_sensor_role(row),
        state=state,
        numeric_value=numeric_value,
        unit=str(row.get("unit_of_measurement") or "").strip() or None,
        last_updated=row.get("last_updated") or row.get("last_changed"),
    )


def _value_text(reading: SensorReading) -> str:
    """Return a compact value and unit string for a sensor reading."""
    value = reading.numeric_value
    if value is None:
        return reading.state
    value_text = f"{value:.1f}".rstrip("0").rstrip(".")
    unit = reading.unit or ("%" if reading.role == "humidity" else "")
    if unit == "%":
        return f"{value_text} percent"
    return f"{value_text}{unit}"


def _temperature_c(reading: SensorReading) -> float:
    """Return a temperature reading converted to Celsius."""
    if reading.numeric_value is None:
        raise ValueError("Temperature reading has no numeric value.")
    unit = _normalise_unit(reading.unit)
    if unit in {"°f", "f"}:
        return (reading.numeric_value - 32.0) * 5.0 / 9.0
    return reading.numeric_value


def _freshness_clause(
    last_updated: datetime | None,
    now: datetime,
    stale_after: timedelta,
) -> str:
    """Return a user-facing freshness sentence."""
    if last_updated is None:
        return " The update time is unknown."
    age = now - last_updated.astimezone(UTC)
    if age > stale_after:
        return (
            f" Home Assistant reports it last updated {_age_text(age)} ago, "
            "so the reading may be stale."
        )
    return f" Home Assistant reports it last updated {_age_text(age)} ago."


def _is_stale(
    last_updated: datetime | None,
    now: datetime,
    stale_after: timedelta,
) -> bool:
    """Return whether a reading is missing freshness or exceeds the threshold."""
    return last_updated is None or now - last_updated.astimezone(UTC) > stale_after


def _age_text(age: timedelta) -> str:
    """Return a compact human-readable age."""
    seconds = max(0, int(age.total_seconds()))
    if seconds < 120:
        return "about 1 minute"
    if seconds < 3600:
        return f"{seconds // 60} minutes"
    hours = seconds / 3600
    if hours < 24:
        return f"{hours:.1f}".rstrip("0").rstrip(".") + " hours"
    days = hours / 24
    return f"{days:.1f}".rstrip("0").rstrip(".") + " days"


def _normalise_prompt(value: Any) -> str:
    """Return lowercase prompt text while retaining apostrophes for parsing."""
    text = str(value or "").lower().strip()
    text = re.sub(r"[^a-z0-9'_.%°\s-]", " ", text)
    return re.sub(r"\s+", " ", text).strip(" .-?")


def _normalise(value: Any) -> str:
    """Return canonical lowercase text for deterministic comparisons."""
    text = re.sub(r"[^a-z0-9_.\s-]", " ", str(value or "").lower())
    return re.sub(r"\s+", " ", text).strip(" .- ")


def _normalise_unit(value: Any) -> str:
    """Return a compact lowercase Home Assistant unit string."""
    return str(value or "").strip().lower().replace(" ", "")


def _json_names(value: Any) -> set[str]:
    """Return canonical names from an area aliases JSON value."""
    if value is None:
        return set()
    if hasattr(value, "read"):
        value = value.read()
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except ValueError:
            return set()
    if not isinstance(value, list):
        return set()
    return {_normalise(item) for item in value if _normalise(item)}


def _timestamp(value: Any) -> datetime | None:
    """Return an aware UTC timestamp from Oracle or ISO timestamp values."""
    if value is None:
        return None
    if isinstance(value, datetime):
        parsed = value
    else:
        try:
            parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        except ValueError:
            return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)
