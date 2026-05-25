"""TTS voice catalogue discovery and selection for Orac."""
# Author: Clive Bostock
# Date: 2026-05-25
# Description: Discovers selectable TTS voices and resolves user preferences.

from __future__ import annotations

from dataclasses import asdict, dataclass, replace
import json
from pathlib import Path
import re
from typing import Any

from loguru import logger
import requests

from lib.config_mgr import ConfigManager
from orac_voice.tts_kokoro import DEFAULT_KOKORO_BASE_URL
from orac_voice.tts_kokoro import DEFAULT_KOKORO_VOICE
from orac_voice.tts_piper import DEFAULT_PIPER_VOICE_DIR
from orac_voice.tts_piper import LEGACY_PIPER_VOICE_DIR
from orac_voice.tts_piper import PACKAGED_PIPER_VOICE_DIR
from orac_voice.tts_piper import expand_config_path


VOICE_SECTION = "voice"
TTS_VOICES_OBJECT = "orac_api.tts_voices_v"
PIPER_PROVIDER = "piper"
KOKORO_PROVIDER = "kokoro"
KNOWN_PIPER_QUALITIES = {"x_low", "low", "medium", "high"}


@dataclass(frozen=True)
class TtsVoiceRow:
  """One selectable TTS voice catalogue row."""

  tts_voice_key: str
  provider_code: str
  provider_voice_id: str
  display_name: str
  language_code: str | None = None
  locale_code: str | None = None
  voice_quality: str | None = None
  model_path: str | None = None
  config_path: str | None = None
  metadata_json: str | None = None
  default_yn: str = "N"
  enabled_yn: str = "Y"
  sort_order: int | None = None

  @classmethod
  def from_db_row(cls, row: dict[str, Any]) -> "TtsVoiceRow":
    """Build a row object from an Oracle dictionary result."""
    return cls(
      tts_voice_key=str(row.get("TTS_VOICE_KEY") or "").strip(),
      provider_code=str(row.get("PROVIDER_CODE") or "").strip().lower(),
      provider_voice_id=str(row.get("PROVIDER_VOICE_ID") or "").strip(),
      display_name=str(row.get("DISPLAY_NAME") or "").strip(),
      language_code=_optional_str(row.get("LANGUAGE_CODE")),
      locale_code=_optional_str(row.get("LOCALE_CODE")),
      voice_quality=_optional_str(row.get("VOICE_QUALITY")),
      model_path=_optional_str(row.get("MODEL_PATH")),
      config_path=_optional_str(row.get("CONFIG_PATH")),
      metadata_json=_clob_to_str(row.get("METADATA_JSON")),
      default_yn=str(row.get("DEFAULT_YN") or "N").strip().upper() or "N",
      enabled_yn=str(row.get("ENABLED_YN") or "Y").strip().upper() or "Y",
      sort_order=_optional_int(row.get("SORT_ORDER")),
    )

  def to_runtime_dict(self) -> dict[str, Any]:
    """Return a JSON-friendly representation for runtime metadata."""
    return asdict(self)


def _optional_str(value: Any) -> str | None:
  """Return a stripped string or None."""
  if value is None:
    return None
  if hasattr(value, "read"):
    value = value.read()
  cleaned = str(value).strip()
  return cleaned or None


def _optional_int(value: Any) -> int | None:
  """Return an int or None."""
  if value in (None, ""):
    return None
  try:
    return int(value)
  except Exception:
    return None


def _clob_to_str(value: Any) -> str | None:
  """Return CLOB-like values as strings."""
  return _optional_str(value)


def _normalise_provider(value: str) -> str:
  """Return a provider code suitable for catalogue keys."""
  return re.sub(r"[^a-z0-9_]+", "", value.strip().lower())


def _voice_key(provider_code: str, provider_voice_id: str) -> str:
  """Build the stable TTS voice key."""
  return f"{_normalise_provider(provider_code)}:{provider_voice_id.strip()}"


def _display_name_from_voice_id(voice_id: str) -> str:
  """Build a readable display name from a provider voice identifier."""
  cleaned = re.sub(r"[_-]+", " ", voice_id).strip()
  return " ".join(part.capitalize() for part in cleaned.split()) or voice_id


def _piper_voice_metadata(voice_id: str) -> tuple[str | None, str | None, str | None]:
  """Infer language, locale, and quality from a Piper voice id."""
  parts = voice_id.split("-")
  locale_code = parts[0] if parts else None
  language_code = None
  if locale_code:
    language_code = locale_code.split("_", 1)[0]
  voice_quality = None
  if len(parts) > 1 and parts[-1].lower() in KNOWN_PIPER_QUALITIES:
    voice_quality = parts[-1].lower()
  return language_code, locale_code, voice_quality


def _configured_piper_dirs(config_mgr: ConfigManager, orac_home: Path) -> list[Path]:
  """Return Piper voice directories using the same fallback order as runtime."""
  raw_voice_dir = config_mgr.config_value(
    VOICE_SECTION,
    "tts_voice_dir",
    default=f"${{ORAC_HOME}}/{DEFAULT_PIPER_VOICE_DIR}",
  )
  configured_dir = expand_config_path(raw_voice_dir, orac_home=orac_home)
  dirs = [configured_dir]
  if configured_dir == orac_home / DEFAULT_PIPER_VOICE_DIR:
    dirs.extend(
      [
        orac_home / PACKAGED_PIPER_VOICE_DIR,
        orac_home / LEGACY_PIPER_VOICE_DIR,
      ]
    )
  return list(dict.fromkeys(dirs))


def discover_piper_voices(
  *,
  config_mgr: ConfigManager,
  orac_home: Path,
) -> list[TtsVoiceRow]:
  """Discover usable Piper voices from configured voice directories."""
  configured_voice = config_mgr.config_value(
    VOICE_SECTION,
    "tts_voice",
    default="",
  ).strip()
  rows: list[TtsVoiceRow] = []
  seen: set[str] = set()

  for voice_dir in _configured_piper_dirs(config_mgr, orac_home):
    if not voice_dir.exists():
      logger.info("Piper voice directory unavailable: {}", voice_dir)
      continue
    for model_path in sorted(voice_dir.rglob("*.onnx")):
      voice_id = model_path.stem
      if voice_id in seen:
        continue
      seen.add(voice_id)
      config_path = model_path.with_suffix(f"{model_path.suffix}.json")
      language_code, locale_code, voice_quality = _piper_voice_metadata(voice_id)
      rows.append(
        TtsVoiceRow(
          tts_voice_key=_voice_key(PIPER_PROVIDER, voice_id),
          provider_code=PIPER_PROVIDER,
          provider_voice_id=voice_id,
          display_name=_display_name_from_voice_id(voice_id),
          language_code=language_code,
          locale_code=locale_code,
          voice_quality=voice_quality,
          model_path=str(model_path),
          config_path=str(config_path) if config_path.exists() else None,
          metadata_json=json.dumps(
            {"voice_dir": str(voice_dir)},
            sort_keys=True,
          ),
          default_yn="Y" if voice_id == configured_voice else "N",
          sort_order=len(rows) + 1,
        )
      )

  if not rows:
    logger.warning("No usable Piper voices discovered.")
  return rows


def build_kokoro_voices_url(base_url: str) -> str:
  """Build the Kokoro voices endpoint URL from a configured base URL."""
  cleaned = (base_url or "").strip().rstrip("/")
  if not cleaned:
    cleaned = DEFAULT_KOKORO_BASE_URL.rstrip("/")
  if cleaned.endswith("/v1"):
    return f"{cleaned}/audio/voices"
  return f"{cleaned}/v1/audio/voices"


def _normalise_kokoro_voice_payload(payload: Any) -> list[dict[str, Any]]:
  """Return voice records from common Kokoro voice-list response shapes."""
  if isinstance(payload, list):
    candidates = payload
  elif isinstance(payload, dict):
    candidates = (
      payload.get("voices")
      or payload.get("data")
      or payload.get("items")
      or []
    )
  else:
    candidates = []

  records: list[dict[str, Any]] = []
  for candidate in candidates:
    if isinstance(candidate, str):
      records.append({"id": candidate})
      continue
    if not isinstance(candidate, dict):
      continue
    voice_id = (
      candidate.get("id")
      or candidate.get("voice")
      or candidate.get("name")
      or candidate.get("voice_id")
    )
    if voice_id:
      record = dict(candidate)
      record["id"] = str(voice_id)
      records.append(record)
  return records


def discover_kokoro_voices(
  *,
  config_mgr: ConfigManager,
  timeout_seconds: float = 2.0,
) -> list[TtsVoiceRow]:
  """Discover Kokoro voices from its OpenAI-compatible local service."""
  base_url = config_mgr.config_value(
    VOICE_SECTION,
    "tts_kokoro_base_url",
    default=DEFAULT_KOKORO_BASE_URL,
  )
  configured_voice = config_mgr.config_value(
    VOICE_SECTION,
    "tts_kokoro_voice",
    default=DEFAULT_KOKORO_VOICE,
  ).strip()
  voices_url = build_kokoro_voices_url(base_url)

  try:
    response = requests.get(voices_url, timeout=timeout_seconds)
    response.raise_for_status()
    records = _normalise_kokoro_voice_payload(response.json())
  except Exception as exc:
    logger.warning("Kokoro voice discovery unavailable at {}: {}", voices_url, exc)
    return []

  rows: list[TtsVoiceRow] = []
  for index, record in enumerate(records, start=1):
    voice_id = str(record.get("id") or "").strip()
    if not voice_id:
      continue
    display_name = str(record.get("display_name") or "").strip()
    rows.append(
      TtsVoiceRow(
        tts_voice_key=_voice_key(KOKORO_PROVIDER, voice_id),
        provider_code=KOKORO_PROVIDER,
        provider_voice_id=voice_id,
        display_name=display_name or _display_name_from_voice_id(voice_id),
        language_code=_optional_str(record.get("language")),
        locale_code=_optional_str(record.get("locale")),
        voice_quality=_optional_str(record.get("quality")),
        metadata_json=json.dumps(record, sort_keys=True),
        default_yn="Y" if voice_id == configured_voice else "N",
        sort_order=index,
      )
    )

  if not rows:
    logger.warning("Kokoro voice discovery returned no usable voices.")
  return rows


def discover_tts_voices(
  *,
  config_mgr: ConfigManager,
  orac_home: Path,
) -> list[TtsVoiceRow]:
  """Discover available voices from every configured TTS provider."""
  rows = [
    *discover_piper_voices(config_mgr=config_mgr, orac_home=orac_home),
    *discover_kokoro_voices(config_mgr=config_mgr),
  ]
  default_key = configured_tts_voice_key(config_mgr)
  if not default_key:
    return rows
  return [
    replace(row, default_yn="Y" if row.tts_voice_key == default_key else "N")
    for row in rows
  ]


def refresh_tts_voice_catalog(
  *,
  db_session: Any,
  config_mgr: ConfigManager,
  orac_home: Path,
) -> list[TtsVoiceRow]:
  """Refresh the database catalogue from discovered TTS providers."""
  rows = discover_tts_voices(config_mgr=config_mgr, orac_home=orac_home)
  if not rows:
    raise RuntimeError("No usable TTS voices discovered.")

  try:
    with db_session.cursor() as cursor:
      cursor.execute(f"delete from {TTS_VOICES_OBJECT}")
      for row in rows:
        cursor.execute(
          f"""
          insert into {TTS_VOICES_OBJECT}
            (tts_voice_key, provider_code, provider_voice_id, display_name,
             language_code, locale_code, voice_quality, model_path,
             config_path, metadata_json, default_yn, enabled_yn, sort_order)
          values
            (:tts_voice_key, :provider_code, :provider_voice_id, :display_name,
             :language_code, :locale_code, :voice_quality, :model_path,
             :config_path, :metadata_json, :default_yn, :enabled_yn, :sort_order)
          """,
          row.to_runtime_dict(),
        )
    db_session.commit()
  except Exception:
    try:
      db_session.rollback()
    except Exception:
      logger.debug("Ignored rollback failure after TTS voice catalogue refresh.")
    raise

  logger.info("TTS voice catalogue refresh complete: {} voice(s)", len(rows))
  return rows


def _row_for_key(db_session: Any, tts_voice_key: str) -> TtsVoiceRow | None:
  """Load an enabled catalogue row by voice key."""
  key = (tts_voice_key or "").strip()
  if not key:
    return None
  rows = db_session.dict_sql_dataset(
    f"""
    select tts_voice_key,
           provider_code,
           provider_voice_id,
           display_name,
           language_code,
           locale_code,
           voice_quality,
           model_path,
           config_path,
           metadata_json,
           default_yn,
           enabled_yn,
           sort_order
      from {TTS_VOICES_OBJECT}
     where tts_voice_key = :tts_voice_key
       and enabled_yn = 'Y'
    """,
    {"tts_voice_key": key},
  )
  if not rows:
    return None
  return TtsVoiceRow.from_db_row(rows[0])


def _default_row(db_session: Any) -> TtsVoiceRow | None:
  """Load the preferred discovered default row."""
  rows = db_session.dict_sql_dataset(
    f"""
    select tts_voice_key,
           provider_code,
           provider_voice_id,
           display_name,
           language_code,
           locale_code,
           voice_quality,
           model_path,
           config_path,
           metadata_json,
           default_yn,
           enabled_yn,
           sort_order
      from {TTS_VOICES_OBJECT}
     where enabled_yn = 'Y'
       and default_yn = 'Y'
     order by provider_code,
              nvl(sort_order, 999999),
              display_name
    """,
  )
  if not rows:
    return None
  return TtsVoiceRow.from_db_row(rows[0])


def configured_tts_voice_key(config_mgr: ConfigManager) -> str | None:
  """Return the voice key implied by current backwards-compatible config."""
  engine = config_mgr.config_value(
    VOICE_SECTION,
    "tts_engine",
    default=PIPER_PROVIDER,
  ).strip().lower()
  if engine == KOKORO_PROVIDER:
    voice_id = config_mgr.config_value(
      VOICE_SECTION,
      "tts_kokoro_voice",
      default=DEFAULT_KOKORO_VOICE,
    ).strip()
    return _voice_key(KOKORO_PROVIDER, voice_id) if voice_id else None

  voice_id = config_mgr.config_value(
    VOICE_SECTION,
    "tts_voice",
    default="",
  ).strip()
  return _voice_key(PIPER_PROVIDER, voice_id) if voice_id else None


def resolve_tts_voice_selection(
  *,
  db_session: Any,
  config_mgr: ConfigManager,
  preferred_voice_key: str | None,
  username: str | None = None,
) -> TtsVoiceRow | None:
  """Resolve the runtime TTS voice for a user preference and config fallback."""
  preferred = (preferred_voice_key or "").strip()
  if preferred:
    row = _row_for_key(db_session, preferred)
    if row is not None:
      return row
    logger.warning(
      "TTS preference '{}' for user '{}' is unavailable; falling back.",
      preferred,
      username or "<unknown>",
    )

  config_key = configured_tts_voice_key(config_mgr)
  if config_key:
    row = _row_for_key(db_session, config_key)
    if row is not None:
      return row
    logger.warning(
      "Configured TTS voice '{}' is unavailable; checking discovered default.",
      config_key,
    )

  row = _default_row(db_session)
  if row is not None:
    return row

  logger.error("No valid TTS voice is available for runtime selection.")
  return None
