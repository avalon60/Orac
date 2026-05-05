"""Local voice support package for Orac.

# Author: Clive Bostock
# Date: 2026-05-04
# Description: Provides local text-to-speech interfaces and workers.
"""

from __future__ import annotations

from orac_voice.audio_capture import AudioCapture, SoundDeviceAudioCapture
from orac_voice.audio_playback import AudioPlayback, LocalAudioPlayback
from orac_voice.stt_faster_whisper import FasterWhisperSttEngine, SttEngine
from orac_voice.tts_piper import PiperTtsEngine
from orac_voice.tts_worker import TtsWorker
from orac_voice.voice_events import (
  VoiceError,
  VoiceSttEnded,
  VoiceSttError,
  VoiceSttFinal,
  VoiceSttStarted,
  VoiceTextChunk,
  VoiceTtsEnded,
  VoiceTtsStarted,
  VoiceTurnCancelled,
)

__all__ = [
  "AudioCapture",
  "AudioPlayback",
  "FasterWhisperSttEngine",
  "LocalAudioPlayback",
  "PiperTtsEngine",
  "SoundDeviceAudioCapture",
  "SttEngine",
  "TtsWorker",
  "VoiceError",
  "VoiceSttEnded",
  "VoiceSttError",
  "VoiceSttFinal",
  "VoiceSttStarted",
  "VoiceTextChunk",
  "VoiceTtsEnded",
  "VoiceTtsStarted",
  "VoiceTurnCancelled",
]
