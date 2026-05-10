"""Experimental STT phrase wake activation for Orac."""
# Author: Clive Bostock
# Date: 2026-05-05
# Description: Provides local STT phrase wake activation for Orac.

from __future__ import annotations

from difflib import SequenceMatcher
from pathlib import Path
import string
import uuid

from loguru import logger

from orac_voice.activation import VoiceActivationResult
from orac_voice.audio_capture import SoundDeviceAudioCapture, VadCaptureResult
from orac_voice.stt_faster_whisper import FasterWhisperSttEngine


FUZZY_WAKE_MATCH_CUTOFF = 0.84
ORAC_WAKE_ALIASES = {
  "orac": {"orac", "orack", "ora", "aurac", "auroc", "aurok"},
  "oracle": {"oracle", "orackle", "auracle"},
}


class SttPhraseWakeWordActivationListener:
  """Experimental wake listener using existing VAD and STT components.

  This is not a true low-power wake-word detector. It records short utterances
  with the existing VAD endpoint detector, transcribes them with faster-whisper,
  and activates only when the recognised text matches the configured phrase.
  """

  def __init__(
    self,
    *,
    wake_phrase: str,
    capture: SoundDeviceAudioCapture,
    stt_engine: FasterWhisperSttEngine,
    exit_phrases: set[str] | None = None,
  ) -> None:
    """Create an experimental STT phrase wake listener.

    Args:
      wake_phrase (str): Comma-separated wake phrase or phrase variants.
      capture (SoundDeviceAudioCapture): Reusable local capture wrapper.
      stt_engine (FasterWhisperSttEngine): Reusable STT wrapper.
      exit_phrases (set[str] | None): Recognised phrases that exit the
        session if heard while waiting for wake activation.
    """
    configured_phrases = _normalise_phrase_set(wake_phrase)
    if not configured_phrases:
      configured_phrases = {"orac"}
    self.display_wake_phrase = sorted(configured_phrases)[0].title()
    self.wake_phrases = _expand_wake_phrases(configured_phrases)
    self.capture = capture
    self.stt_engine = stt_engine
    self.exit_phrases = exit_phrases or set()
    self._closed = False

  @property
  def display_phrase(self) -> str:
    """Return the primary phrase for console display."""
    return self.display_wake_phrase

  def wait_for_activation(self, *, session_id: str) -> VoiceActivationResult:
    """Listen for and transcribe a short wake phrase utterance."""
    if self._closed:
      return VoiceActivationResult(
        activated=False,
        exit_requested=True,
        reason="wake listener closed",
        wake_engine="stt_phrase",
      )

    print(f"Listening for wake word: {self.display_phrase}", flush=True)
    turn_id = f"wake-{uuid.uuid4().hex[:12]}"
    try:
      result = self.capture.record_until_silence_to_wav(
        session_id=session_id,
        turn_id=turn_id,
      )
    except KeyboardInterrupt:
      self.capture.cancel()
      raise

    if result.no_speech_timeout or result.wav_path is None:
      return VoiceActivationResult(
        activated=False,
        reason="no wake speech detected",
        wake_engine="stt_phrase",
      )

    recognised = self._transcribe_wake_phrase(result.wav_path)
    normalised = _normalise_phrase(recognised)
    if normalised in self.exit_phrases:
      return VoiceActivationResult(
        activated=False,
        exit_requested=True,
        reason="spoken exit phrase",
        wake_engine="stt_phrase",
      )
    if _matches_wake_phrase(normalised, self.wake_phrases):
      print("Wake word detected.", flush=True)
      return VoiceActivationResult(
        activated=True,
        reason="wake phrase recognised",
        wake_phrase=recognised,
        wake_engine="stt_phrase",
      )

    logger.debug("Wake phrase ignored: {}", recognised)
    return VoiceActivationResult(
      activated=False,
      reason="wake phrase not recognised",
      wake_phrase=recognised,
      wake_engine="stt_phrase",
    )

  def close(self) -> None:
    """Release activation resources."""
    self._closed = True
    self.capture.cancel()

  def _transcribe_wake_phrase(self, wav_path: Path) -> str:
    """Transcribe a captured wake phrase WAV file."""
    try:
      return self.stt_engine.transcribe_wav(wav_path).strip()
    except Exception as exc:
      raise RuntimeError(f"Wake phrase transcription failed: {exc}") from exc


def _normalise_phrase_set(value: str) -> set[str]:
  """Normalise a comma-separated phrase list."""
  return {
    normalised
    for phrase in value.split(",")
    if (normalised := _normalise_phrase(phrase))
  }


def _expand_wake_phrases(wake_phrases: set[str]) -> set[str]:
  """Expand configured wake phrases with known STT variants."""
  expanded = set(wake_phrases)
  for phrase in wake_phrases:
    expanded.update(ORAC_WAKE_ALIASES.get(phrase, set()))
  return expanded


def _normalise_phrase(value: str) -> str:
  """Normalise recognised wake phrase text for comparison."""
  cleaned = value.strip().lower()
  cleaned = cleaned.translate(str.maketrans("", "", string.punctuation))
  return " ".join(cleaned.split())


def _matches_wake_phrase(text: str, wake_phrases: set[str]) -> bool:
  """Return whether recognised text contains a configured wake phrase."""
  wake_phrases = _expand_wake_phrases(wake_phrases)
  if text in wake_phrases:
    return True
  padded = f" {text} "
  if any(f" {phrase} " in padded for phrase in wake_phrases):
    return True

  tokens = text.split()
  phrase_tokens = {
    phrase
    for phrase in wake_phrases
    if " " not in phrase and len(phrase) >= 3
  }
  return any(
    SequenceMatcher(None, token, phrase).ratio() >= FUZZY_WAKE_MATCH_CUTOFF
    for token in tokens
    for phrase in phrase_tokens
  )
