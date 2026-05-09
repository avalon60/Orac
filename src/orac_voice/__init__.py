"""Local voice support package for Orac.

# Author: Clive Bostock
# Date: 2026-05-04
# Description: Provides local text-to-speech interfaces and workers.
"""

from __future__ import annotations

from orac_voice.activation import EnterActivationListener
from orac_voice.activation import VoiceActivationError
from orac_voice.activation import VoiceActivationListener
from orac_voice.activation import VoiceActivationResult
from orac_voice.activation import WakeWordActivationListener
from orac_voice.audio_capture import AudioCapture, SoundDeviceAudioCapture
from orac_voice.audio_playback import AudioPlayback, LocalAudioPlayback
from orac_voice.barge_in import BargeInConfig
from orac_voice.barge_in import BargeInController
from orac_voice.barge_in import BargeInResult
from orac_voice.interruption_policy import InterruptionAction
from orac_voice.interruption_policy import InterruptionDecision
from orac_voice.interruption_policy import InterruptionPolicy
from orac_voice.interruption_policy import InterruptionState
from orac_voice.stt_faster_whisper import FasterWhisperSttEngine, SttEngine
from orac_voice.tts_coalescer import TtsChunkCoalescer
from orac_voice.tts_piper import PiperTtsEngine
from orac_voice.tts_worker import TtsWorker
from orac_voice.wake_openwakeword import OpenWakeWordActivationListener
from orac_voice.wake_porcupine import PorcupineActivationListener
from orac_voice.wake_stt_phrase import SttPhraseWakeWordActivationListener
from orac_voice.voice_events import (
  VoiceError,
  VoiceSttEnded,
  VoiceSttError,
  VoiceSttFinal,
  VoiceSttStarted,
  VoiceTextChunk,
  VoiceTtsEnded,
  VoiceTtsPlaybackCancelled,
  VoiceTtsPlaybackError,
  VoiceTtsPlaybackFinished,
  VoiceTtsPlaybackStarted,
  VoiceTtsStarted,
  VoiceTurnCancelled,
  VoiceVadError,
  VoiceVadListeningStarted,
  VoiceVadSpeechEnded,
  VoiceVadSpeechStarted,
  VoiceVadTimeout,
)

__all__ = [
  "AudioCapture",
  "AudioPlayback",
  "BargeInConfig",
  "BargeInController",
  "BargeInResult",
  "InterruptionAction",
  "InterruptionDecision",
  "InterruptionPolicy",
  "InterruptionState",
  "EnterActivationListener",
  "FasterWhisperSttEngine",
  "LocalAudioPlayback",
  "OpenWakeWordActivationListener",
  "PiperTtsEngine",
  "PorcupineActivationListener",
  "SoundDeviceAudioCapture",
  "SttEngine",
  "SttPhraseWakeWordActivationListener",
  "TtsChunkCoalescer",
  "TtsWorker",
  "VoiceActivationError",
  "VoiceActivationListener",
  "VoiceActivationResult",
  "VoiceError",
  "VoiceSttEnded",
  "VoiceSttError",
  "VoiceSttFinal",
  "VoiceSttStarted",
  "VoiceTextChunk",
  "VoiceTtsEnded",
  "VoiceTtsPlaybackCancelled",
  "VoiceTtsPlaybackError",
  "VoiceTtsPlaybackFinished",
  "VoiceTtsPlaybackStarted",
  "VoiceTtsStarted",
  "VoiceTurnCancelled",
  "VoiceVadError",
  "VoiceVadListeningStarted",
  "VoiceVadSpeechEnded",
  "VoiceVadSpeechStarted",
  "VoiceVadTimeout",
  "WakeWordActivationListener",
]
