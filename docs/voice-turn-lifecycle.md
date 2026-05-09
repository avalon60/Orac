# Voice Turn Lifecycle

This document defines the local Orac voice contract from wake-word detection through STT, prompt streaming, TTS playback, barge-in, cancellation, error handling, and return to wake-listening.

It is intentionally strict. The local voice client has been refactored around a moving target; this document captures the contract the implementation should obey, even where the current code only approximates it.

Relevant files:

- `src/orac_voice/voice_loop_local.py`
- `src/controller/orac.py`
- `src/orac_voice/tts_worker.py`
- `src/orac_voice/tts_coalescer.py`
- `src/orac_voice/barge_in.py`
- `src/orac_voice/audio_playback.py`
- `src/view/slave.py`
- `protocol/orac_protocol/resources/json_schema/protocol.schema.json`
- `tests/test_orac_voice.py`
- `tests/test_display_event_pipe.py`

## Scope

The local voice loop has two distinct responsibilities:

1. Detect wake words, capture user speech, and submit a prompt.
2. Observe Orac's streaming and TTS lifecycle closely enough to keep the UI, barge-in, and re-arming state correct.

The display is a thin visual endpoint. It must not own turn logic.

## Canonical State Machine

These are the logical states for the local voice client and the display.

### `wake_listening`

- Meaning: the system is waiting for a wake word.
- Display: show `idle` with the message `Listening for wake word`.
- Enter from: `idle/rearming`, `error/recovering`, `cancelling`, `interrupted` after cleanup, or startup `initialising`.
- Exit to: `recording` on wake activation.
- Barge-in: stopped.

### `recording`

- Meaning: the wake word has fired and the microphone is capturing user speech.
- Display: show `listening`.
- Enter from: `wake_listening`.
- Exit to: `transcribing` when speech ends or capture times out.
- Barge-in: still stopped unless the current turn is already speaking, which it is not at this stage.

### `transcribing`

- Meaning: captured audio is being transcribed to text.
- Display: usually remains `listening` or can remain unchanged; the user is still in a capture phase.
- Enter from: `recording`.
- Exit to: `thinking` when the prompt is sent, or back to `wake_listening` if no speech was captured.

### `thinking`

- Meaning: the prompt has been submitted and the client is waiting for Orac's response stream.
- Display: show `thinking`.
- Enter from: `transcribing` after a non-empty user utterance is accepted.
- Exit to: `speaking` on the first `tts_playback_started`, or to `idle/rearming` on a true non-speaking completion, or to `error/recovering`.
- Barge-in: must not start yet.

### `speaking`

- Meaning: at least one utterance for the current turn is queued or playing.
- Display: show `speaking`.
- Enter from: `thinking` on `tts_playback_started`.
- Exit to: `interrupted` on barge-in, `cancelling` on cancellation, `idle/rearming` on true turn completion, or `error/recovering` on error.
- Barge-in: active for the entire speaking period, including pauses between utterances.

### `interrupted`

- Meaning: user speech has been detected while Orac was speaking.
- Display: show `interrupted`.
- Enter from: `speaking` when barge-in fires.
- Exit to: `cancelling` while the client sends the cancel request, then to `idle/rearming` or `recording` depending on barge-in return mode.
- Barge-in: stop the monitor exactly once as part of interruption cleanup.

### `cancelling`

- Meaning: the current turn is being cancelled and the system is draining or discarding queued speech.
- Display: may remain `interrupted` until cleanup completes.
- Enter from: `interrupted` or a direct cancel path.
- Exit to: `idle/rearming` when cancellation is complete, or to `error/recovering` if the cancel path fails.
- Barge-in: stopped.

### `idle/rearming`

- Meaning: the current voice turn is complete and the system is ready to listen again.
- Display: show `idle` with the message `Listening for wake word`.
- Enter from: true turn completion, cancel completion, or recoverable failure.
- Exit to: `wake_listening` immediately, or after any configured wake re-arm delay.
- Barge-in: stopped.

### `error/recovering`

- Meaning: the turn or session encountered a protocol, playback, or transport error that is recoverable at the session level.
- Display: show `error`.
- Enter from: protocol validation errors, playback errors, stream errors, or cancellation failures.
- Exit to: `idle/rearming` if the session can continue, or to process exit if the error is unrecoverable.
- Barge-in: stopped.

### Display-only states

The atom display also supports `sleeping` and `shutdown`.

- `sleeping` is a visual low-power state, not a voice-turn state.
- `shutdown` is a terminal process-exit state and should not be used as a synonym for "finished speaking".

## Protocol Event Table

The table below documents the contract for the events that matter to the local voice loop.

| Event | Producer | Consumer | Granularity | Terminal | May arrive before final response text? | Affects display? | Starts or stops barge-in? |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `request` | local voice client | Orac controller | per-turn | no | n/a, it is the start of the turn | yes, usually `thinking` after send | no |
| `stream_start` | Orac controller | local voice client | per-turn | no | yes | no direct state change | no |
| `text_delta` | Orac controller | local voice client | per-token | no | yes | no direct state change | no |
| `text_chunk` | Orac controller, after TTS coalescing/queueing | local voice client, TTS lifecycle logic | per-text-chunk | no | yes | no direct state change | no |
| `stream_end` | Orac controller | local voice client | per-turn | yes for the text stream only | yes | no direct state change | no |
| `stream_error` | Orac controller | local voice client | per-turn | yes for the text stream only | yes | yes, `error` | no |
| `stream_cancelled` | Orac controller | local voice client | per-turn | yes for the text stream only | yes | yes, usually `interrupted` or `error` | no |
| `response` | Orac controller | local voice client | per-turn | no | yes, it may arrive before all playback events | no direct state change | no |
| `tts_playback_started` | TTS worker / playback owner | local voice client, display, barge-in monitor | per-utterance | no | yes | yes, `speaking` | start barge-in |
| `tts_playback_finished` | TTS worker / playback owner | local voice client, display, turn-complete aggregator | per-utterance | no | yes | no direct state change | do not stop barge-in by itself |
| `tts_playback_cancelled` | TTS worker / playback owner or cancel path | local voice client, display, turn-complete aggregator | per-utterance | yes for that utterance | yes | yes, usually `interrupted` or `error` | stop barge-in if the current turn is no longer speaking |
| `tts_playback_error` | TTS worker / playback owner | local voice client, display, turn-complete aggregator | per-utterance | yes for that utterance | yes | yes, `error` | stop barge-in |
| `voice_turn_complete` | turn-completion owner | local voice client, display | per-turn | yes | should arrive after all playback events for the turn | yes, `idle` | stop barge-in exactly once |
| `voice_cancel_request` | local voice client | Orac controller | per-turn | no | n/a | no direct display state | no |
| `voice_cancel_response` | Orac controller | local voice client | per-turn | yes for the cancel transaction, not for the spoken turn unless followed by a terminal voice turn frame | no | may drive `interrupted` or `error` cleanup | no |

### Notes on event meaning

- `text_chunk` is not proof that audio has been queued. It is only a speech candidate. Queueing may be delayed, merged, flushed later, or rejected.
- `response` is not proof that speech is complete. It is only the final model response frame.
- `tts_playback_finished` means one utterance finished. It does not mean the turn finished.
- `voice_turn_complete` means the full spoken turn is complete, including any queued utterances and their playback lifecycle.

## Ownership Rule for Completion

The local client must treat completion as a single owned responsibility, not a heuristic.

The only component allowed to emit `voice_turn_complete` is the component that can prove the TTS queue and playback lifecycle for the current turn have fully drained, or have been fully cancelled.

That means the owner must know, at minimum:

- how many utterances were accepted for the turn,
- how many have actually started,
- how many have actually finished or been cancelled,
- whether any additional utterances can still be flushed from the coalescer,
- whether cancellation has fully discarded the pending turn.

### Why this matters

- `text_chunk` does not tell you whether the audio exists yet.
- `response` does not tell you whether the audio has started or finished.
- `tts_playback_finished` only closes one utterance, not the turn.

### Current ownership reality

`src/controller/orac.py` currently approximates this ownership by subscribing to playback events and maintaining counters.

That is a useful approximation, but it is not a proof. The controller does not own the audio device clock directly; `src/orac_voice/tts_worker.py` and `src/orac_voice/audio_playback.py` own the actual synthesis/playback boundary.

If the system needs a truly authoritative turn-complete signal, the emission point should move closer to the TTS worker or to a dedicated lifecycle aggregator built on top of it.

## Barge-in Rules

The lifecycle contract and the acoustic reality are different problems.
The lifecycle can be correct while the microphone still hears Orac's own
TTS output as user speech. That is an acoustic reliability failure, not a
turn-completion failure.

On ordinary speakers without echo cancellation, both `vad` barge-in and
`openwakeword` barge-in are unsafe. They can self-trigger on assistant
speech.

Supported modes:

- Stable mode: `barge_in_enabled=false`
- Experimental mode: `barge_in_enabled=true`,
  `barge_in_mode=vad`,
  `barge_in_acknowledge_self_trigger_risk=true`
- Reliable full-duplex mode: headphones, a directional mic, echo
  cancellation, or another physically separate audio path

### When the monitor starts

- Start barge-in only when the current turn begins speaking.
- In practice, that is on the first `tts_playback_started` for the turn.
- Do not start barge-in on `stream_start`, `text_delta`, `text_chunk`, or `response`.

### When the monitor stops

- Stop barge-in exactly once when the current turn is fully complete, cancelled, or failed.
- Do not stop barge-in on `tts_playback_finished`.
- Do not stop barge-in during a short pause between utterances.

### What happens on interruption

- The monitor callback marks the turn as interrupted.
- The client sends a cancel request for the active turn.
- Queued TTS for the turn is drained or discarded.
- The turn must still end in a terminal turn event after cancellation cleanup.

### What happens to queued TTS

- Any queued but not yet spoken utterances for the cancelled turn must be discarded.
- Any in-flight playback must be cancelled if possible.
- Late-arriving chunks for the cancelled turn must be rejected.

### Terminal event after cancellation

There is no dedicated `voice_turn_cancelled` frame in the current protocol schema.

That is a contract gap.

Today, the system uses `tts_playback_cancelled` at the utterance level and then relies on the turn owner to emit `voice_turn_complete` after cancellation cleanup. That is workable, but overloaded.

If the implementation needs to distinguish natural completion from cancellation at the protocol level, the schema should grow a dedicated terminal cancel event. Until then, `voice_turn_complete` remains the only turn terminal.

### Why `openwakeword` barge-in is disabled on speakers

`openwakeword` barge-in is unsafe on ordinary speakers because it listens for the wake word while Orac itself is speaking.

Without strong echo cancellation or headphones, it will false-trigger on Orac's own output and cancel the active turn. That is a model-level property of the setup, not a cosmetic bug.

For live interruption on speakers, `vad` barge-in is the safer mode because it detects generic user speech instead of wake-word identity.

### How VAD barge-in should behave

- Listen only while Orac is speaking.
- Ignore an initial grace window so the start of Orac's own speech is not treated as user speech.
- Fire only on sustained user speech.
- Stay active through pauses between utterances.
- Stop only once, at terminal turn completion or cancellation.
- It is only reliable on speaker playback when the audio path can
  suppress echo or otherwise isolate Orac's output from the microphone.

## Required Invariants

These are the rules the implementation must preserve.

- The client must never infer turn completion from `text_chunk`.
- The client must never infer full turn completion from a single `tts_playback_finished`.
- The display must stay `speaking` while any utterance for the current turn is queued, playing, or still cancellable.
- The display must return to wake-listening promptly after true turn completion.
- Barge-in must remain active throughout speaking, including pauses between utterances.
- Barge-in must be stopped exactly once on turn completion, cancellation, or unrecoverable error.
- A cancelled turn must drain or discard queued TTS and still emit a terminal turn event.
- A failed turn must return to wake-listening without exiting the voice session.

## Observed Race Conditions

These races have already been seen in the current implementation history and must be treated as design constraints, not anecdotes.

- The client returned on a nonzero status with no traceback.
- `openwakeword` self-triggered on Orac's own speech.
- The final response arrived before all playback events.
- `tts_playback_finished` was mistaken for turn completion.
- `voice_turn_complete` fired before later queued speech.
- The barge-in monitor stopped during pauses between utterances.
- The barge-in monitor could remain live after interruption.

## Current Implementation Risks

The following are places where the current code appears to violate or only approximate the contract.

### `src/controller/orac.py`

- `voice_turn_complete` is emitted here, but this module does not own the audio device and cannot truly prove that playback has drained.
- Completion is inferred from playback counters and stream state. That is better than guessing from text alone, but it is still a heuristic.
- `text_chunk` is treated as an indicator that playback is expected, which is useful for coordination, but not proof that audio exists.
- Any future change in coalescing or queueing order can invalidate the current counters without changing the wire protocol.

### `src/orac_voice/voice_loop_local.py`

- The prompt loop still has direct-return error exits for timeout, invalid JSON, unexpected protocol frames, and server errors.
- Those exits rely on cleanup paths outside the branch that detected the error, which makes the terminal state machine easy to break again.
- The client still maintains some local inference state such as `playback_expected` and `playback_finished_count`. That state is necessary for now, but it is not a proof of completion.
- The loop must keep barge-in active across the entire speaking period, including pauses between utterances. Any early stop in a future edit would violate the contract immediately.
- The loop currently treats `voice_turn_complete` as the authoritative idle point, which is correct only if the event itself is emitted after all playback has actually drained.

### `src/orac_voice/tts_worker.py`

- This module owns the TTS queue and the playback process, so it is the closest thing to an authoritative utterance boundary.
- It emits `VoiceTtsPlaybackFinished` after `AudioPlayback.play_wav()` returns, which is the best audible completion boundary in the current design.
- It does not currently emit a dedicated turn-level terminal event; that responsibility lives above it.

### `src/orac_voice/tts_coalescer.py`

- The coalescer can hold back chunks and later flush them as a different utterance boundary than the original `text_chunk`.
- That means chunk events are not equivalent to utterance events.
- Any completion logic that assumes one `text_chunk` equals one utterance is wrong.

### `src/orac_voice/barge_in.py`

- The module supports both `vad` and `openwakeword`, but the local voice
  client intentionally disables `openwakeword` barge-in on speakers.
- VAD barge-in is also unsafe on ordinary speakers unless the audio path
  can suppress echo or isolate Orac's own voice from the microphone.
- The barge-in contract is therefore partly policy-driven, not purely
  config-driven, and the stable default is to leave barge-in disabled.

### `src/orac_voice/audio_playback.py`

- `LocalAudioPlayback.play_wav()` blocks until the playback process returns, which is a good completion boundary for the local desktop case.
- It still depends on the external player behaving honestly.
- The component owns playback, but not a rich turn lifecycle.

### `src/view/slave.py`

- The client accepts `voice_turn_complete` as a stream event and uses it as a session-rearm signal.
- If the server ever emits that frame before the final utterance has really finished, the client will re-arm too early.

### `protocol/orac_protocol/resources/json_schema/protocol.schema.json`

- The schema includes `voice_turn_complete`, but not a separate terminal cancel event for turns.
- That means cancellation and natural completion are overloaded onto the same terminal turn concept.

### `tests/test_orac_voice.py`

- The current tests pin many of the playback and barge-in transitions, but they still depend on synthetic event ordering.
- They do not prove that the physical speaker output is drained before re-arming.

### `tests/test_display_event_pipe.py`

- The display pipe is best-effort and fire-and-forget.
- It intentionally does not participate in turn correctness.

## Recommended Implementation Plan

This is the minimal ordered patch plan that would make the contract real without adding new timeouts as a substitute for protocol correctness.

1. Move turn-complete ownership to the component that truly owns the TTS queue and playback lifecycle, or add a thin lifecycle aggregator directly above it.
2. Make `voice_turn_complete` the only turn-level re-arm signal consumed by the local voice client and display.
3. Remove any remaining completion inference from `text_chunk`, `response`, or a single `tts_playback_finished`.
4. Keep barge-in active across the whole speaking window, including pauses between utterances, and stop it only on true terminal turn cleanup.
5. Decide whether the protocol should gain a dedicated terminal cancel event. If not, document the overloaded use of `voice_turn_complete` explicitly.
6. Tighten tests around multi-utterance turns, cancellation, and pause-between-utterances behavior so regressions become visible immediately.

## Summary Contract

The short version is:

- Wake-listening is `idle`.
- STT capture is `listening`.
- Prompt submission is `thinking`.
- Any queued or playing speech is `speaking`.
- `text_chunk` is a speech candidate, not proof of queueing.
- `tts_playback_finished` is one utterance only.
- `voice_turn_complete` is the only full-turn completion frame.
- Barge-in must stay active until the turn is truly over.
- Cancellation must drain or discard queued speech and still end in a terminal turn event.
