"""Turn-level protocol controller for local Orac voice sessions."""
# Author: Clive Bostock
# Date: 2026-05-25
# Description: Coordinates one local voice turn from prompt send through
#   stream, playback, cancellation, and display state handling.

from __future__ import annotations

import asyncio
import json
import time
from collections.abc import Callable
from typing import Protocol

from loguru import logger

from orac_voice.barge_in import BargeInController
from orac_voice.barge_in import BargeInResult
from orac_voice.barge_in import OpenWakeWordBargeInController
from orac_voice.interruption_policy import InterruptionAction
from orac_voice.interruption_policy import InterruptionPolicy
from view.display_event_pipe import DisplayEventSender


ConsoleLineWriter = Callable[[str], None]
ConsoleStartWriter = Callable[[str], None]


class VoiceCancelRequester(Protocol):
  """Callable interface for sending a voice cancellation request."""

  async def __call__(
    self,
    *,
    host: str,
    port: int,
    session_id: str,
    turn_id: str | None,
    reason: str,
  ) -> None:
    """Send a best-effort cancellation request."""
    ...


class VoiceTurnController:
  """Coordinate protocol frames and state transitions for one voice turn."""

  def __init__(
    self,
    *,
    reader: asyncio.StreamReader,
    writer: asyncio.StreamWriter,
    prompt_text: str,
    barge_in_controller: BargeInController | None = None,
    voice_session_id: str | None = None,
    cancel_host: str = "127.0.0.1",
    cancel_port: int = 8765,
    display_sender: DisplayEventSender | None = None,
    cancel_request: VoiceCancelRequester | None = None,
    console_line: ConsoleLineWriter | None = None,
    console_start: ConsoleStartWriter | None = None,
  ) -> None:
    """Initialise a voice turn controller.

    Args:
      reader (asyncio.StreamReader): Connected Orac protocol reader.
      writer (asyncio.StreamWriter): Connected Orac protocol writer.
      prompt_text (str): User prompt text to send to Orac.
      barge_in_controller (BargeInController | None): Optional local
        interruption detector.
      voice_session_id (str | None): Local voice session identifier.
      cancel_host (str): Orac host used for best-effort cancellation.
      cancel_port (int): Orac port used for best-effort cancellation.
      display_sender (DisplayEventSender | None): Optional display bridge.
      cancel_request (VoiceCancelRequester | None): Cancellation transport.
      console_line (ConsoleLineWriter | None): Console line writer.
      console_start (ConsoleStartWriter | None): Console prefix writer.
    """
    self.reader = reader
    self.writer = writer
    self.prompt_text = prompt_text
    self.barge_in_controller = barge_in_controller
    self.voice_session_id = voice_session_id
    self.cancel_host = cancel_host
    self.cancel_port = cancel_port
    self.display_sender = display_sender
    self.cancel_request = cancel_request
    self.console_line = console_line or print
    self.console_start = console_start or self._default_console_start

  async def run(self) -> int:
    """Send the prompt and process protocol frames until the turn finishes."""
    from view import slave as slave_client

    barge_in_controller = self.barge_in_controller
    if (
      barge_in_controller is not None
      and not getattr(barge_in_controller.config, "enabled", True)
    ):
      barge_in_controller = None

    req_env = slave_client.build_prompt_request(
      self.prompt_text,
      session_id=self.voice_session_id,
    )
    req_id = str(req_env.get("id") or "")
    wire = json.dumps(req_env, ensure_ascii=False) + "\n"
    self.writer.write(wire.encode("utf-8"))
    await self.writer.drain()
    request_sent_at = time.perf_counter()
    _send_display_event(
      self.display_sender,
      "transcript.orac.start",
      session_id=self.voice_session_id,
      turn_id=req_id,
    )
    if self.display_sender is not None:
      self.display_sender.send_state(
        "thinking",
        message="Thinking...",
        session_id=self.voice_session_id,
        turn_id=req_id,
      )

    stream_rendered = False
    stream_finished = False
    stream_error_seen = False
    barge_active = False
    playback_expected = False
    playback_started_count = 0
    playback_cancelled = False
    final_response_status: int | None = None
    orac_transcript_parts: list[str] = []
    stream_start_at: float | None = None
    first_text_delta_at: float | None = None
    first_text_chunk_at: float | None = None
    stream_end_at: float | None = None
    first_tts_started_at: float | None = None
    last_tts_finished_at: float | None = None
    timing_logged = False
    barge_in_min_speech_ms = 0
    last_runtime_identity: tuple[str, str, str, str] | None = None
    if (
      barge_in_controller is not None
      and not isinstance(barge_in_controller, OpenWakeWordBargeInController)
    ):
      barge_in_min_speech_ms = getattr(
        barge_in_controller.config,
        "min_speech_ms",
        0,
      )
    interruption_policy = InterruptionPolicy(
      allow_interruptions=barge_in_controller is not None,
      min_speech_ms=barge_in_min_speech_ms,
    )
    barge_event = asyncio.Event()
    barge_result: BargeInResult | None = None
    loop = asyncio.get_running_loop()

    def _on_barge_in(result: BargeInResult) -> None:
      nonlocal barge_result
      decision = interruption_policy.consider_acoustic_interrupt(
        output_turn_id=req_id,
        speech_ms=result.speech_ms,
      )
      if decision.action is not InterruptionAction.INTERRUPT:
        logger.debug(
          "Ignoring acoustic interruption for turn {}: {}",
          req_id,
          decision.reason,
        )
        return
      barge_result = result
      loop.call_soon_threadsafe(barge_event.set)

    def _start_barge_in_monitor() -> None:
      nonlocal barge_active
      if barge_active or barge_in_controller is None:
        return
      barge_active = True
      barge_event.clear()
      barge_in_controller.reset_for_speech()
      barge_in_controller.start(on_interrupt=_on_barge_in)

    def _stop_barge_in_monitor() -> None:
      nonlocal barge_active
      if not barge_active or barge_in_controller is None:
        return
      barge_active = False
      barge_in_controller.stop()

    def _elapsed_since_request(value: float | None) -> float | None:
      """Return elapsed seconds from the prompt send point."""
      if value is None:
        return None
      return value - request_sent_at

    def _format_timing(value: float | None) -> str:
      """Format an optional elapsed duration for logs."""
      if value is None:
        return "n/a"
      return f"{value:.2f}s"

    def _log_response_timing(reason: str) -> None:
      """Log one compact response timing summary for this turn."""
      nonlocal timing_logged
      if timing_logged:
        return
      timing_logged = True
      logger.info(
        (
          "Voice response timing: session={} turn={} reason={} "
          "stream_start={} first_text={} first_speech_chunk={} "
          "stream_end={} first_audio={} playback_done={} total={} "
          "tts_parts={}"
        ),
        self.voice_session_id or "",
        req_id,
        reason,
        _format_timing(_elapsed_since_request(stream_start_at)),
        _format_timing(_elapsed_since_request(first_text_delta_at)),
        _format_timing(_elapsed_since_request(first_text_chunk_at)),
        _format_timing(_elapsed_since_request(stream_end_at)),
        _format_timing(_elapsed_since_request(first_tts_started_at)),
        _format_timing(_elapsed_since_request(last_tts_finished_at)),
        _format_timing(time.perf_counter() - request_sent_at),
        playback_started_count,
      )

    def _maybe_finish_turn() -> int | None:
      """Return the final status once the answer and playback are complete."""
      if playback_cancelled:
        interruption_policy.mark_turn_complete(output_turn_id=req_id)
        if self.display_sender is not None:
          self.display_sender.send_state(
            "idle",
            message="Listening for wake word",
            session_id=self.voice_session_id,
            turn_id=req_id,
          )
        _stop_barge_in_monitor()
        _log_response_timing("cancelled")
        return final_response_status if final_response_status is not None else 0
      if final_response_status is None:
        return None
      if not stream_finished:
        return None
      interruption_policy.mark_turn_complete(output_turn_id=req_id)
      if self.display_sender is not None:
        self.display_sender.send_state(
          "idle",
          message="Listening for wake word",
          session_id=self.voice_session_id,
          turn_id=req_id,
        )
      _stop_barge_in_monitor()
      _log_response_timing("response")
      return final_response_status

    async def _cancel_interrupted_voice() -> int:
      logger.info("Barge-in interruption received; cancelling active voice")
      self.console_line("[interrupted]")
      if self.display_sender is not None:
        self.display_sender.send_state(
          "interrupted",
          message="Interrupted",
          session_id=self.voice_session_id,
          turn_id=req_id,
        )
      _stop_barge_in_monitor()
      interruption_policy.mark_output_cancelled(output_turn_id=req_id)
      if self.cancel_request is not None:
        await self.cancel_request(
          host=self.cancel_host,
          port=self.cancel_port,
          session_id=self.voice_session_id or "",
          turn_id=req_id,
          reason=(barge_result.reason if barge_result else "barge-in"),
        )
      _log_response_timing("interrupted")
      return 0

    async def _read_response_line():
      line_task = asyncio.create_task(self.reader.readline())
      wait_tasks = {line_task}
      barge_task = None
      if barge_in_controller is not None:
        barge_task = asyncio.create_task(barge_event.wait())
        wait_tasks.add(barge_task)
      done, pending = await asyncio.wait(
        wait_tasks,
        timeout=(
          60.0
          if final_response_status is not None and playback_expected
          else 5.0
          if final_response_status is not None
          else slave_client.LLM_TIMEOUT
        ),
        return_when=asyncio.FIRST_COMPLETED,
      )
      for task in pending:
        task.cancel()
      if not done:
        return "timeout", None
      if barge_task is not None and barge_task in done and barge_event.is_set():
        if not line_task.done():
          line_task.cancel()
        return "interrupted", None
      if line_task in done:
        return "line", line_task.result()
      return "timeout", None

    try:
      while True:
        read_status, resp_bytes = await _read_response_line()
        if read_status == "timeout":
          self.console_line("Orac response timed out.")
          _log_response_timing("timeout")
          if self.display_sender is not None:
            self.display_sender.send_state(
              "error",
              message="Orac response timed out",
              session_id=self.voice_session_id,
              turn_id=req_id,
            )
          return 1
        if read_status == "interrupted":
          return await _cancel_interrupted_voice()

        if not resp_bytes:
          if final_response_status is not None:
            if self.display_sender is not None:
              self.display_sender.send_state(
                "idle",
                message="Listening for wake word",
                session_id=self.voice_session_id,
                turn_id=req_id,
              )
            _stop_barge_in_monitor()
            _log_response_timing("connection-closed")
            return final_response_status
          return 0

        response_text = resp_bytes.decode("utf-8", errors="replace").strip()
        try:
          env = json.loads(response_text)
        except json.JSONDecodeError as exc:
          logger.error("Invalid JSON from Orac: {}", exc)
          self.console_line("Invalid protocol frame from Orac.")
          _log_response_timing("invalid-json")
          return 1

        frame_reply_to = env.get("reply_to")
        if frame_reply_to and req_id and str(frame_reply_to) != req_id:
          logger.debug(
            "Skipping stale Orac frame for reply_to={} while awaiting {}",
            frame_reply_to,
            req_id,
          )
          continue

        runtime_identity = _display_runtime_identity_from_frame(env)
        if (
          self.display_sender is not None
          and runtime_identity is not None
          and runtime_identity != last_runtime_identity
        ):
          model, persona, personality_code, personality_name = runtime_identity
          _send_display_event(
            self.display_sender,
            "runtime.identity",
            session_id=self.voice_session_id,
            turn_id=req_id,
            model=model,
            persona=persona,
            personality_code=personality_code,
            personality_name=personality_name,
          )
          last_runtime_identity = runtime_identity

        frame_type = env.get("type")
        if frame_type in slave_client.STREAM_EVENT_TYPES:
          if frame_type == "tts_playback_error":
            if not interruption_policy.accept_output_event(output_turn_id=req_id):
              logger.debug(
                "Ignoring stale playback event {} for turn {}",
                frame_type,
                req_id,
              )
              continue
            err_obj = env.get("error")
            msg = ""
            if isinstance(err_obj, dict):
              msg = str(err_obj.get("message") or "")
            logger.warning("TTS playback error: {}", msg or "unknown")
            interruption_policy.mark_output_cancelled(output_turn_id=req_id)
            if self.display_sender is not None:
              self.display_sender.send_state(
                "error",
                message=msg or "TTS playback error",
                session_id=self.voice_session_id,
                turn_id=req_id,
              )
            _stop_barge_in_monitor()
            continue
          err_obj = env.get("error")
          if isinstance(err_obj, dict) and err_obj:
            stream_error_seen = True
            code = err_obj.get("code", "SERVER_ERROR")
            msg = err_obj.get("message", "Unknown error")
            if stream_rendered:
              print()
            self.console_line(f"[stream error] {code}: {msg}")
            continue

          payload = env.get("payload")
          payload = payload if isinstance(payload, dict) else {}
          if frame_type == "stream_start":
            if stream_start_at is None:
              stream_start_at = time.perf_counter()
            self.console_start("Orac: ")
            stream_rendered = True
          elif frame_type == "text_delta":
            if first_text_delta_at is None:
              first_text_delta_at = time.perf_counter()
            if not stream_rendered:
              self.console_start("Orac: ")
              stream_rendered = True
            delta = payload.get("delta", "")
            delta_text = slave_client.strip_reasoning_tags_from_delta(
              str(delta)
            )
            if delta_text:
              orac_transcript_parts.append(delta_text)
              _send_display_event(
                self.display_sender,
                "transcript.orac.delta",
                session_id=self.voice_session_id,
                turn_id=req_id,
                text=delta_text,
              )
            print(
              delta_text,
              end="",
              flush=True,
            )
          elif frame_type == "text_chunk":
            if first_text_chunk_at is None:
              first_text_chunk_at = time.perf_counter()
            logger.debug("Speech text chunk received for existing TTS path")
            playback_expected = True
          elif frame_type in {"stream_end", "stream_cancelled"}:
            stream_end_at = time.perf_counter()
            stream_finished = True
            if stream_rendered:
              print()
            if frame_type == "stream_cancelled":
              self.console_line("[stream cancelled]")
          elif frame_type == "tts_playback_started":
            playback_started_count += 1
            if first_tts_started_at is None:
              first_tts_started_at = time.perf_counter()
            playback_expected = True
            interruption_policy.begin_output_turn(output_turn_id=req_id)
            self.console_line("TTS playback started.")
            if self.display_sender is not None:
              self.display_sender.send_state(
                "speaking",
                message="Speaking",
                session_id=self.voice_session_id,
                turn_id=req_id,
              )
            if barge_in_controller is not None:
              logger.info("TTS playback started; enabling barge-in monitor")
              _start_barge_in_monitor()
            else:
              logger.debug("TTS playback started")
            continue
          elif frame_type in {
            "tts_playback_finished",
            "tts_playback_cancelled",
            "tts_playback_error",
          }:
            if not interruption_policy.accept_output_event(output_turn_id=req_id):
              logger.debug(
                "Ignoring stale playback event {} for turn {}",
                frame_type,
                req_id,
              )
              continue
            self.console_line(f"{frame_type} received.")
            logger.debug("{} received", frame_type)
            if frame_type == "tts_playback_cancelled":
              playback_cancelled = True
              interruption_policy.mark_output_cancelled(output_turn_id=req_id)
              maybe_status = _maybe_finish_turn()
              _stop_barge_in_monitor()
              if maybe_status is not None:
                return maybe_status
              continue
            if frame_type == "tts_playback_finished":
              last_tts_finished_at = time.perf_counter()
              interruption_policy.mark_output_finished(output_turn_id=req_id)
              continue
          elif frame_type == "voice_turn_complete":
            interruption_policy.mark_turn_complete(output_turn_id=req_id)
            if last_tts_finished_at is None:
              last_tts_finished_at = time.perf_counter()
            if self.display_sender is not None:
              self.display_sender.send_state(
                "idle",
                message="Listening for wake word",
                session_id=self.voice_session_id,
                turn_id=req_id,
              )
            _stop_barge_in_monitor()
            _log_response_timing("voice-complete")
            return 1 if stream_error_seen else 0
          continue

        if frame_type != "response":
          self.console_line("Unexpected protocol frame from Orac.")
          _log_response_timing("unexpected-frame")
          return 1

        err_obj = env.get("error")
        if isinstance(err_obj, dict) and err_obj:
          _log_response_timing("server-error")
          if not stream_error_seen:
            code = err_obj.get("code", "SERVER_ERROR")
            msg = err_obj.get("message", "Unknown error")
            self.console_line(f"[server error] {code}: {msg}")
            if self.display_sender is not None:
              self.display_sender.send_state(
                "error",
                message=str(msg),
                session_id=self.voice_session_id,
                turn_id=req_id,
              )
          return 1

        payload = env.get("payload")
        content = payload.get("content") if isinstance(payload, dict) else ""
        final_text = slave_client.strip_reasoning_tags(str(content))
        if not final_text:
          final_text = "".join(orac_transcript_parts).strip()
        if stream_end_at is None and not stream_rendered:
          stream_end_at = time.perf_counter()
        _send_display_event(
          self.display_sender,
          "transcript.orac.final",
          session_id=self.voice_session_id,
          turn_id=req_id,
          text=final_text,
        )
        if stream_rendered or stream_finished:
          print()
          final_response_status = 1 if stream_error_seen else 0
          if not stream_finished:
            logger.debug(
              "Final response received; waiting for stream_end event"
            )
            continue
          if playback_expected:
            logger.debug(
              "Final response received; waiting for remaining playback events"
            )
            continue
          maybe_status = _maybe_finish_turn()
          if maybe_status is not None:
            return maybe_status
          continue

        self.console_line(f"Orac: {final_text}")
        if self.display_sender is not None:
          self.display_sender.send_state(
            "idle",
            message="Listening for wake word",
            session_id=self.voice_session_id,
            turn_id=req_id,
          )
        _log_response_timing("response")
        return 0
    finally:
      _stop_barge_in_monitor()

  @staticmethod
  def _default_console_start(text: str) -> None:
    """Write a console prefix without a newline."""
    print(text, end="", flush=True)


def _send_display_event(
  display_sender: DisplayEventSender | None,
  event: str,
  *,
  session_id: str | None = None,
  turn_id: str | None = None,
  **payload: object,
) -> None:
  """Emit one lightweight display event if the display pipe is enabled."""
  if display_sender is None:
    return

  event_payload: dict[str, object] = {
    "event": event,
  }
  if session_id is not None:
    event_payload["session_id"] = session_id
  if turn_id is not None:
    event_payload["turn_id"] = turn_id
  for key, value in payload.items():
    if value is not None:
      event_payload[key] = value
  display_sender.send(event_payload)


def _display_runtime_identity_from_frame(
  frame: dict[str, object],
) -> tuple[str, str, str, str] | None:
  """Extract the current LLM/persona identity from an Orac frame."""
  meta = frame.get("meta")
  if not isinstance(meta, dict):
    return None

  model = str(meta.get("model") or "").strip()
  personality_code = str(meta.get("personality_code") or "").strip().upper()
  personality_name = str(meta.get("personality_name") or "").strip()
  persona = personality_name or personality_code
  if model and not persona:
    personality_code = "DEFAULT"
    persona = personality_code
  if not model and not persona:
    return None
  return model, persona, personality_code, personality_name
