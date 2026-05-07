"""Porcupine wake-word activation for Orac."""
# Author: Clive Bostock
# Date: 2026-05-05
# Description: Provides Porcupine wake-word activation for Orac.

from __future__ import annotations

from pathlib import Path

from lib.api_key_store import ApiKeyStore, ApiKeyStoreError
from orac_voice.activation import VoiceActivationError
from orac_voice.activation import VoiceActivationResult
from orac_voice.tts_piper import expand_config_path, resolve_orac_home


DEFAULT_PORCUPINE_ACCESS_KEY_RESOURCE = "picovoice/access_key"
MIN_PICOVOICE_ACCESS_KEY_LENGTH = 20


class PorcupineActivationListener:
  """Production wake-word listener backed by Picovoice Porcupine."""

  def __init__(
    self,
    *,
    access_key_resource: str = DEFAULT_PORCUPINE_ACCESS_KEY_RESOURCE,
    keyword_path: str = "",
    builtin_keyword: str = "",
    sensitivity: float = 0.6,
    input_device_index: int | None = None,
    key_store: ApiKeyStore | None = None,
  ) -> None:
    """Create a Porcupine wake-word listener.

    Args:
      access_key_resource (str): API key store resource name.
      keyword_path (str): Optional custom Porcupine ``.ppn`` keyword path.
      builtin_keyword (str): Optional built-in Porcupine keyword.
      sensitivity (float): Porcupine sensitivity in the range 0 to 1.
      input_device_index (int | None): Optional PvRecorder device index.
      key_store (ApiKeyStore | None): Optional key store override for tests.
    """
    self.access_key_resource = access_key_resource.strip()
    self.keyword_path = _resolve_optional_path(keyword_path)
    self.builtin_keyword = builtin_keyword.strip().lower()
    self.sensitivity = float(sensitivity)
    self.input_device_index = input_device_index
    self.key_store = key_store
    self._porcupine = None
    self._recorder = None
    self._closed = False

  def wait_for_activation(self, *, session_id: str) -> VoiceActivationResult:
    """Listen continuously until Porcupine detects the wake word."""
    del session_id
    if self._closed:
      return VoiceActivationResult(
        activated=False,
        exit_requested=True,
        reason="porcupine listener closed",
        wake_engine="porcupine",
      )

    porcupine = self._create_porcupine()
    recorder = self._create_recorder(frame_length=porcupine.frame_length)
    print("Listening for wake word: Porcupine", flush=True)
    try:
      recorder.start()
      while not self._closed:
        pcm = recorder.read()
        keyword_index = porcupine.process(pcm)
        if keyword_index >= 0:
          print("Wake word detected.", flush=True)
          return VoiceActivationResult(
            activated=True,
            reason="porcupine keyword detected",
            wake_engine="porcupine",
          )
    except KeyboardInterrupt:
      self.close()
      raise
    except VoiceActivationError:
      raise
    except Exception as exc:
      raise VoiceActivationError(
        f"Porcupine wake-word listener failed: {exc}"
      ) from exc
    finally:
      self._stop_recorder()

    return VoiceActivationResult(
      activated=False,
      exit_requested=True,
      reason="porcupine listener stopped",
      wake_engine="porcupine",
    )

  def close(self) -> None:
    """Release Porcupine and microphone resources."""
    self._closed = True
    self._stop_recorder()
    if self._porcupine is not None:
      try:
        self._porcupine.delete()
      finally:
        self._porcupine = None

  def _create_porcupine(self):
    """Create or return the cached Porcupine engine."""
    if self._porcupine is not None:
      return self._porcupine
    try:
      import pvporcupine
    except ImportError as exc:
      raise VoiceActivationError(
        "wake_engine=porcupine requires the pvporcupine package. Install "
        "the Porcupine wake dependencies, then retry."
      ) from exc

    access_key = self._load_access_key()
    kwargs = {
      "access_key": access_key,
      "sensitivities": [self.sensitivity],
    }
    if self.keyword_path:
      if not self.keyword_path.exists():
        raise VoiceActivationError(
          f"Porcupine keyword file does not exist: {self.keyword_path}"
        )
      kwargs["keyword_paths"] = [str(self.keyword_path)]
    elif self.builtin_keyword:
      keywords = getattr(pvporcupine, "KEYWORDS", set())
      if self.builtin_keyword not in keywords:
        raise VoiceActivationError(
          f"Porcupine built-in keyword '{self.builtin_keyword}' is not "
          "available. Configure porcupine_keyword_path with a custom .ppn "
          "file for 'Hey Orac' or 'Orac'."
        )
      kwargs["keywords"] = [self.builtin_keyword]
    else:
      raise VoiceActivationError(
        "Porcupine wake-word mode requires porcupine_keyword_path or "
        "porcupine_builtin_keyword. For 'Hey Orac' or 'Orac', create a "
        "custom .ppn in Picovoice Console and store it under "
        "${ORAC_HOME}/var/models/wake."
      )

    try:
      self._porcupine = pvporcupine.create(**kwargs)
    except Exception as exc:
      raise VoiceActivationError(
        "Unable to initialise Porcupine wake-word engine. Check the "
        "Picovoice AccessKey and keyword configuration."
      ) from exc
    return self._porcupine

  def _create_recorder(self, *, frame_length: int):
    """Create a PvRecorder instance for Porcupine frame input."""
    try:
      from pvrecorder import PvRecorder
    except ImportError as exc:
      raise VoiceActivationError(
        "wake_engine=porcupine requires the pvrecorder package. Install "
        "the Porcupine wake dependencies, then retry."
      ) from exc

    try:
      self._recorder = PvRecorder(
        frame_length=frame_length,
        device_index=self.input_device_index,
      )
    except Exception as exc:
      raise VoiceActivationError(
        f"Unable to open microphone for Porcupine wake detection: {exc}"
      ) from exc
    return self._recorder

  def _load_access_key(self) -> str:
    """Load the Picovoice AccessKey without logging it."""
    try:
      key_store = self.key_store or ApiKeyStore()
      access_key = key_store.get_api_key(self.access_key_resource).strip()
    except ApiKeyStoreError as exc:
      raise VoiceActivationError(
        f"Picovoice AccessKey is missing. {exc}"
      ) from exc
    if len(access_key) < MIN_PICOVOICE_ACCESS_KEY_LENGTH:
      raise VoiceActivationError(
        "Picovoice AccessKey is configured but looks incomplete. Re-store "
        "the full AccessKey from Picovoice Console; do not store it in "
        "orac.ini."
      )
    return access_key

  def _stop_recorder(self) -> None:
    """Stop and release the active PvRecorder safely."""
    if self._recorder is None:
      return
    try:
      self._recorder.stop()
    except Exception:
      pass
    try:
      self._recorder.delete()
    finally:
      self._recorder = None


def _resolve_optional_path(value: str) -> Path | None:
  """Resolve an optional config path."""
  cleaned = value.strip()
  if not cleaned:
    return None
  return expand_config_path(cleaned, orac_home=resolve_orac_home())
