"""Tests for selectable TTS voice catalogue support."""
# Author: Clive Bostock
# Date: 2026-05-25
# Description: Verifies TTS voice schema, discovery, and runtime selection.

from __future__ import annotations

import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch


PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
  sys.path.insert(0, str(SRC_ROOT))

from orac_voice.tts_voice_catalog import TtsVoiceRow
from orac_voice.tts_voice_catalog import discover_piper_voices
from orac_voice.tts_voice_catalog import refresh_tts_voice_catalog
from orac_voice.tts_voice_catalog import resolve_tts_voice_selection
import orac_voice.tts_voice_catalog as catalog_module
import orac_voice.tts_worker as tts_worker_module


SCHEMA_ROOT = PROJECT_ROOT / "resources" / "db" / "schema"
CORE_ROOT = SCHEMA_ROOT / "orac_core"
CODE_ROOT = SCHEMA_ROOT / "orac_code"


class _FakeConfig:
  """Small config stand-in for catalogue tests."""

  def __init__(self, values: dict[tuple[str, str], str]) -> None:
    self.values = values

  def config_value(self, section: str, key: str, default: str = "") -> str:
    """Return a configured value or default."""
    return self.values.get((section, key), default)


class _FakeCursor:
  """Recording cursor for refresh tests."""

  def __init__(self) -> None:
    self.statements: list[tuple[str, dict | None]] = []

  def __enter__(self) -> "_FakeCursor":
    return self

  def __exit__(self, exc_type, exc, tb) -> None:
    return None

  def execute(self, sql: str, params: dict | None = None) -> None:
    """Record executed SQL."""
    self.statements.append((sql, params))


class _FakeDBSession:
  """Fake DB session for selector and refresh tests."""

  def __init__(self, rows: list[dict] | None = None) -> None:
    self.rows = rows or []
    self.cursor_obj = _FakeCursor()
    self.committed = False
    self.rolled_back = False

  def cursor(self) -> _FakeCursor:
    """Return the recording cursor."""
    return self.cursor_obj

  def dict_sql_dataset(self, sql: str, params: dict | None = None) -> list[dict]:
    """Return rows matching simple selector predicates."""
    sql_lower = sql.lower()
    if "where tts_voice_key = :tts_voice_key" in sql_lower:
      key = (params or {}).get("tts_voice_key")
      return [
        row
        for row in self.rows
        if row["TTS_VOICE_KEY"] == key and row.get("ENABLED_YN", "Y") == "Y"
      ]
    if "default_yn = 'y'" in sql_lower:
      return [
        row
        for row in self.rows
        if row.get("DEFAULT_YN") == "Y" and row.get("ENABLED_YN", "Y") == "Y"
      ]
    return list(self.rows)

  def commit(self) -> None:
    """Record commit."""
    self.committed = True

  def rollback(self) -> None:
    """Record rollback."""
    self.rolled_back = True


class TtsVoiceSchemaTests(unittest.TestCase):
  """Static checks for TTS voice database artifacts."""

  def test_tts_voices_table_uses_required_columns_and_soft_reference_key(self) -> None:
    """The catalogue table should match the requested soft-reference shape."""
    table_sql = (CORE_ROOT / "table" / "tts_voices.sql").read_text(
      encoding="utf-8"
    ).lower()
    pk_sql = (CORE_ROOT / "constraint_pk" / "tts_voice_pk.sql").read_text(
      encoding="utf-8"
    ).lower()

    self.assertIn("create table orac_core.tts_voices", table_sql)
    self.assertIn("tts_voice_key    varchar2(300 char) not null", table_sql)
    self.assertIn("provider_code    varchar2(30 char) not null", table_sql)
    self.assertIn("provider_voice_id varchar2(240 char) not null", table_sql)
    self.assertIn("metadata_json    clob", table_sql)
    self.assertNotIn("generated", table_sql)
    self.assertNotIn("identity", table_sql)
    self.assertIn("primary key (tts_voice_key)", pk_sql)

  def test_tts_voice_preference_has_no_hard_foreign_key(self) -> None:
    """User preferences should not hard-reference the runtime catalogue."""
    fk_dir = CORE_ROOT / "constraint_fk"
    combined_fk_sql = "\n".join(
      path.read_text(encoding="utf-8").lower()
      for path in sorted(fk_dir.glob("*.sql"))
    )

    self.assertNotIn("tts_voices", combined_fk_sql)

  def test_user_preference_constraint_allows_empty_string_json_scalar(self) -> None:
    """The preference type check should allow optional empty string values."""
    constraint_sql = (
      CORE_ROOT / "constraint_other" / "user_pref_ck1.sql"
    ).read_text(encoding="utf-8").lower()

    self.assertIn('value_type = \'string\'', constraint_sql)
    self.assertIn(
      'json_exists(pref_value, \'$?(@.type() == "string")\')',
      constraint_sql,
    )
    self.assertNotIn(
      "json_value(pref_value, '$' returning varchar2(4000) null on error) is not null",
      constraint_sql,
    )

  def test_user_preference_api_allows_empty_string_json_scalar(self) -> None:
    """The preference API should not reject optional empty string text."""
    package_sql = (
      CODE_ROOT / "package_body" / "user_preferences_api.sql"
    ).read_text(encoding="utf-8").lower()

    self.assertIn(
      'json_exists(p_pref_value, \'$?(@.type() == "string")\')',
      package_sql,
    )
    self.assertIn("and l_is_string_value <> 'y'", package_sql)


class TtsVoiceCatalogTests(unittest.TestCase):
  """Runtime catalogue and selection tests."""

  def test_discovers_piper_voices_from_configured_directory(self) -> None:
    """Piper discovery should add provider-prefixed voice keys."""
    with tempfile.TemporaryDirectory() as tmp_name:
      root = Path(tmp_name)
      voice_dir = root / "voices"
      voice_dir.mkdir()
      (voice_dir / "en_GB-southern_english_female-low.onnx").write_bytes(b"")
      (voice_dir / "en_GB-southern_english_female-low.onnx.json").write_text(
        "{}",
        encoding="utf-8",
      )
      config = _FakeConfig(
        {
          ("voice", "tts_voice"): "en_GB-southern_english_female-low",
          ("voice", "tts_voice_dir"): str(voice_dir),
        }
      )

      rows = discover_piper_voices(config_mgr=config, orac_home=root)

    self.assertEqual(len(rows), 1)
    self.assertEqual(
      rows[0].tts_voice_key,
      "piper:en_GB-southern_english_female-low",
    )
    self.assertEqual(rows[0].provider_code, "piper")
    self.assertEqual(rows[0].locale_code, "en_GB")
    self.assertEqual(rows[0].voice_quality, "low")

  def test_refresh_loads_discovered_catalogue_rows(self) -> None:
    """Refresh should delete and reload through the API view."""
    db = _FakeDBSession()
    config = _FakeConfig({})
    discovered = [
      TtsVoiceRow(
        tts_voice_key="kokoro:af_heart",
        provider_code="kokoro",
        provider_voice_id="af_heart",
        display_name="Af Heart",
      )
    ]

    with patch.object(
      catalog_module,
      "discover_tts_voices",
      return_value=discovered,
    ):
      rows = refresh_tts_voice_catalog(
        db_session=db,
        config_mgr=config,
        orac_home=PROJECT_ROOT,
      )

    self.assertEqual(rows, discovered)
    self.assertTrue(db.committed)
    self.assertIn(
      "delete from orac_api.tts_voices_v",
      db.cursor_obj.statements[0][0],
    )
    self.assertIn(
      "insert into orac_api.tts_voices_v",
      db.cursor_obj.statements[1][0],
    )
    self.assertEqual(
      db.cursor_obj.statements[1][1]["tts_voice_key"],
      "kokoro:af_heart",
    )

  def test_resolves_valid_user_preference_first(self) -> None:
    """A valid stored preference should win over the configured default."""
    db = _FakeDBSession(
      rows=[
        {
          "TTS_VOICE_KEY": "kokoro:af_heart",
          "PROVIDER_CODE": "kokoro",
          "PROVIDER_VOICE_ID": "af_heart",
          "DISPLAY_NAME": "Af Heart",
          "ENABLED_YN": "Y",
          "DEFAULT_YN": "N",
        },
        {
          "TTS_VOICE_KEY": "piper:old_voice",
          "PROVIDER_CODE": "piper",
          "PROVIDER_VOICE_ID": "old_voice",
          "DISPLAY_NAME": "Old Voice",
          "ENABLED_YN": "Y",
          "DEFAULT_YN": "Y",
        },
      ]
    )
    config = _FakeConfig(
      {
        ("voice", "tts_engine"): "piper",
        ("voice", "tts_voice"): "old_voice",
      }
    )

    row = resolve_tts_voice_selection(
      db_session=db,
      config_mgr=config,
      preferred_voice_key="kokoro:af_heart",
      username="clive",
    )

    self.assertIsNotNone(row)
    self.assertEqual(row.provider_code, "kokoro")
    self.assertEqual(row.provider_voice_id, "af_heart")

  def test_falls_back_to_orac_ini_when_user_preference_unavailable(self) -> None:
    """Invalid user preferences should be treated as soft references."""
    db = _FakeDBSession(
      rows=[
        {
          "TTS_VOICE_KEY": "piper:configured",
          "PROVIDER_CODE": "piper",
          "PROVIDER_VOICE_ID": "configured",
          "DISPLAY_NAME": "Configured",
          "ENABLED_YN": "Y",
          "DEFAULT_YN": "Y",
        }
      ]
    )
    config = _FakeConfig(
      {
        ("voice", "tts_engine"): "piper",
        ("voice", "tts_voice"): "configured",
      }
    )

    row = resolve_tts_voice_selection(
      db_session=db,
      config_mgr=config,
      preferred_voice_key="missing:nope",
      username="clive",
    )

    self.assertIsNotNone(row)
    self.assertEqual(row.tts_voice_key, "piper:configured")

  def test_falls_back_to_default_when_preference_is_null(self) -> None:
    """Null preferences should fall through to the configured/default voice."""
    db = _FakeDBSession(
      rows=[
        {
          "TTS_VOICE_KEY": "kokoro:af_heart",
          "PROVIDER_CODE": "kokoro",
          "PROVIDER_VOICE_ID": "af_heart",
          "DISPLAY_NAME": "Af Heart",
          "ENABLED_YN": "Y",
          "DEFAULT_YN": "Y",
        }
      ]
    )
    config = _FakeConfig(
      {
        ("voice", "tts_engine"): "piper",
        ("voice", "tts_voice"): "missing",
      }
    )

    row = resolve_tts_voice_selection(
      db_session=db,
      config_mgr=config,
      preferred_voice_key=None,
      username="clive",
    )

    self.assertIsNotNone(row)
    self.assertEqual(row.tts_voice_key, "kokoro:af_heart")

  def test_selected_provider_routes_to_matching_engine(self) -> None:
    """Provider code should choose the TTS adapter, not global tts_engine."""
    config = _FakeConfig({("voice", "tts_fallback_engine"): "none"})
    with patch.object(
      tts_worker_module,
      "_create_kokoro_engine",
      return_value="kokoro-engine",
    ) as kokoro_factory, patch.object(
      tts_worker_module,
      "_create_piper_engine",
      return_value="piper-engine",
    ) as piper_factory:
      engine = tts_worker_module._create_tts_engine_for_voice_selection(
        selection={
          "tts_voice_key": "kokoro:af_heart",
          "provider_code": "kokoro",
          "provider_voice_id": "af_heart",
        },
        config_mgr=config,
        config_path=PROJECT_ROOT / "resources" / "config" / "orac.ini",
        voice_dir=None,
      )

    self.assertEqual(engine, "kokoro-engine")
    kokoro_factory.assert_called_once()
    piper_factory.assert_not_called()

  def test_kokoro_discovery_parses_voice_endpoint(self) -> None:
    """Kokoro discovery should accept the service voice-list shape."""
    config = _FakeConfig(
      {
        ("voice", "tts_kokoro_base_url"): "http://127.0.0.1:8880/v1",
        ("voice", "tts_kokoro_voice"): "af_heart",
      }
    )

    class _Response:
      def raise_for_status(self) -> None:
        return None

      def json(self) -> dict:
        return {"voices": [{"id": "af_heart", "display_name": "Heart"}]}

    with patch.object(catalog_module.requests, "get", return_value=_Response()):
      rows = catalog_module.discover_kokoro_voices(config_mgr=config)

    self.assertEqual(rows[0].tts_voice_key, "kokoro:af_heart")
    self.assertEqual(json.loads(rows[0].metadata_json)["id"], "af_heart")


if __name__ == "__main__":
  unittest.main()
