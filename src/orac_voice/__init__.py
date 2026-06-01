"""Local voice support package for Orac.

# Author: Clive Bostock
# Date: 2026-05-09
# Description: Provides local text-to-speech interfaces and workers.
"""

from __future__ import annotations

from orac_voice.aec import AEC_BYTES_PER_FRAME
from orac_voice.aec import AEC_CHANNELS
from orac_voice.aec import AEC_FRAME_DURATION_MS
from orac_voice.aec import AEC_SAMPLE_RATE
from orac_voice.aec import AEC_SAMPLE_WIDTH_BYTES
from orac_voice.aec import AEC_SAMPLES_PER_FRAME
from orac_voice.aec import AcousticEchoCanceller
from orac_voice.aec import LiveKitAcousticEchoCanceller
from orac_voice.aec import NullAcousticEchoCanceller
from orac_voice.aec import create_aec_adapter_from_config
from orac_voice.aec import create_aec_backend
from orac_voice.aec import validate_aec_frame
from orac_voice.aec import validate_aec_frame_format
from orac_voice.activation import EnterActivationListener
from orac_voice.activation import VoiceActivationError
from orac_voice.activation import VoiceActivationListener
from orac_voice.activation import VoiceActivationResult
from orac_voice.activation import WakeWordActivationListener
from orac_voice.audio_capture import AudioCapture, SoundDeviceAudioCapture
from orac_voice.audio_playback import AudioPlayback, LocalAudioPlayback
from orac_voice.audio_playback import NativeAudioPlayback
from orac_voice.audio_playback import PlaybackFrameHandler
from orac_voice.playback_reference_resampler import PlaybackReferenceFrameHandler
from orac_voice.playback_reference_resampler import PlaybackReferenceResampler
from orac_voice.barge_in import BargeInConfig
from orac_voice.barge_in import BargeInController
from orac_voice.barge_in import BargeInResult
from orac_voice.interruption_policy import InterruptionAction
from orac_voice.interruption_policy import InterruptionDecision
from orac_voice.interruption_policy import InterruptionPolicy
from orac_voice.interruption_policy import InterruptionState
from orac_voice.stt_faster_whisper import FasterWhisperSttEngine, SttEngine
from orac_voice.tts_coalescer import TtsChunkCoalescer
from orac_voice.tts_kokoro import KokoroTtsEngine
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
  "AEC_BYTES_PER_FRAME",
  "AEC_CHANNELS",
  "AEC_FRAME_DURATION_MS",
  "AEC_SAMPLE_RATE",
  "AEC_SAMPLE_WIDTH_BYTES",
  "AEC_SAMPLES_PER_FRAME",
  "AcousticEchoCanceller",
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
  "KokoroTtsEngine",
  "LocalAudioPlayback",
  "LiveKitAcousticEchoCanceller",
  "NativeAudioPlayback",
  "NullAcousticEchoCanceller",
  "OpenWakeWordActivationListener",
  "PiperTtsEngine",
  "PorcupineActivationListener",
  "PlaybackFrameHandler",
  "PlaybackReferenceFrameHandler",
  "PlaybackReferenceResampler",
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
  "create_aec_adapter_from_config",
  "create_aec_backend",
  "validate_aec_frame",
  "validate_aec_frame_format",
]
