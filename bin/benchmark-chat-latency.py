#!/usr/bin/env python3
"""Measure signed Orac chat and direct Ollama streaming latency."""

# Author: Clive Bostock
# Date: 04-Oct-2026
# Description: Benchmarks isolated chat turns and records per-frame timings.
# Purpose: Compare interactive Orac latency with direct Ollama inference.
# Usage: bin/benchmark-chat-latency.py --model llama3.1-64K:latest --output-dir /tmp/orac-latency

from __future__ import annotations

import argparse
import asyncio
import base64
import csv
from datetime import datetime, timezone
import hashlib
import hmac
import json
import os
from pathlib import Path
import secrets
import time
import urllib.request
import uuid


PROMPTS = (
    "Hi",
    "Explain in two paragraphs how Python context managers work.",
)


def canonical_json(value: object) -> bytes:
    """Serialize a value using the Orac HMAC canonical form."""
    return json.dumps(value, separators=(",", ":"), sort_keys=True,
                      ensure_ascii=False).encode("utf-8")


def signed_request(prompt: str, user: str, secret: bytes, model: str) -> dict:
    """Build one signed request with a fresh isolated conversation session."""
    route = "orac.prompt"
    payload = {"messages": [{"role": "system", "content": "you are orac."},
                            {"role": "user", "content": prompt}]}
    timestamp = int(time.time())
    nonce = secrets.token_hex(16)
    digest = hashlib.sha256(canonical_json(payload)).hexdigest()
    signature = base64.b64encode(hmac.new(
        secret, f"{user}|{timestamp}|{nonce}|{route}|{digest}".encode(),
        hashlib.sha256).digest()).decode("ascii")
    return {
        "v": 1, "type": "request", "id": f"req-{uuid.uuid4().hex}",
        "ts": datetime.now(timezone.utc).isoformat(), "route": route,
        "meta": {"client": f"latency-{uuid.uuid4().hex}", "model": model,
                 "stream": True, "channel": "text", "show_reasoning": False,
                 "auth": {"scheme": "hmac-v1", "user": user, "ts": timestamp,
                          "nonce": nonce, "sig": signature}},
        "payload": payload, "error": None,
    }


async def benchmark_orac(prompt: str, host: str, port: int, user: str,
                         secret: bytes, timeout: float, model: str) -> dict:
    """Record every NDJSON frame through the terminal response."""
    request = signed_request(prompt, user, secret, model)
    reader, writer = await asyncio.wait_for(asyncio.open_connection(host, port), timeout)
    started = time.perf_counter()
    frames: list[dict] = []
    selected_model = None
    try:
        writer.write(canonical_json(request) + b"\n")
        await writer.drain()
        sent_ms = (time.perf_counter() - started) * 1000
        while True:
            line = await asyncio.wait_for(reader.readline(), timeout)
            if not line:
                raise ConnectionError("Orac closed before the terminal response")
            frame = json.loads(line)
            if frame.get("type") == "response":
                selected_model = (frame.get("meta") or {}).get("model")
            elapsed_ms = (time.perf_counter() - started) * 1000
            frames.append({"type": frame.get("type"), "elapsed_ms": round(elapsed_ms, 3),
                           "error": frame.get("error")})
            if frame.get("type") == "response":
                break
    finally:
        writer.close()
        await writer.wait_closed()
    first = next((f["elapsed_ms"] for f in frames if f["type"] == "text_delta"), None)
    end = next((f["elapsed_ms"] for f in frames if f["type"] == "stream_end"), None)
    return {"source": "orac", "request_id": request["id"], "sent_ms": round(sent_ms, 3),
            "ttft_ms": first, "stream_end_ms": end,
            "total_ms": frames[-1]["elapsed_ms"], "selected_model": selected_model,
            "frames": frames}


def benchmark_ollama(prompt: str, model: str, endpoint: str, timeout: float,
                     num_predict: int, keep_alive: str) -> dict:
    """Measure direct native Ollama streaming using a minimal prompt."""
    payload = {"model": model, "messages": [{"role": "system", "content": "you are orac."},
                                            {"role": "user", "content": prompt}],
               "stream": True, "keep_alive": keep_alive, "think": False,
               "options": {"num_predict": num_predict}}
    request = urllib.request.Request(
        endpoint.rstrip("/") + "/api/chat", data=canonical_json(payload),
        headers={"Content-Type": "application/json"}, method="POST")
    started = time.perf_counter()
    first_ms = None
    terminal = {}
    with urllib.request.urlopen(request, timeout=timeout) as response:
        for line in response:
            chunk = json.loads(line)
            if first_ms is None and (chunk.get("message") or {}).get("content"):
                first_ms = round((time.perf_counter() - started) * 1000, 3)
            if chunk.get("done"):
                terminal = chunk
                break
    result = {"source": "ollama_minimal", "ttft_ms": first_ms,
              "total_ms": round((time.perf_counter() - started) * 1000, 3)}
    for key in ("load_duration", "prompt_eval_duration", "eval_duration",
                "total_duration", "prompt_eval_count", "eval_count"):
        result[key] = terminal.get(key)
    return result


def model_details(endpoint: str, model: str, timeout: float) -> dict:
    """Read the installed model digest and current residency without changing it."""
    with urllib.request.urlopen(endpoint.rstrip("/") + "/api/tags", timeout=timeout) as response:
        tags = json.load(response)
    with urllib.request.urlopen(endpoint.rstrip("/") + "/api/ps", timeout=timeout) as response:
        resident = json.load(response)
    match = next((item for item in tags.get("models", []) if item.get("name") == model), {})
    return {"digest": match.get("digest"), "details": match.get("details"),
            "resident_before": any(item.get("name") == model
                                   for item in resident.get("models", []))}


async def run(args: argparse.Namespace) -> None:
    """Run warm-ups and measured isolated requests, then save JSON and CSV."""
    secret = args.secret_file.read_bytes().strip() if args.include_orac else b""
    metadata = model_details(args.ollama_url, args.model, args.timeout)
    rows: list[dict] = []
    for prompt in PROMPTS:
        for source in (("orac",) if args.orac_only else
                       ("orac", "ollama_minimal") if args.include_orac else
                       ("ollama_minimal",)):
            for index in range(args.warmups + args.repetitions):
                try:
                    if source == "orac":
                        result = await benchmark_orac(prompt, args.host, args.port,
                                                      args.user, secret, args.timeout,
                                                      args.model)
                    else:
                        result = await asyncio.to_thread(
                            benchmark_ollama, prompt, args.model, args.ollama_url,
                            args.timeout, args.num_predict, args.keep_alive)
                except Exception as exc:
                    result = {"source": source, "error": f"{type(exc).__name__}: {exc}"}
                result.update({"prompt": prompt, "model_requested": args.model,
                               "iteration": index + 1,
                               "warmup": index < args.warmups})
                rows.append(result)
                print(f"{source} {args.model} {prompt!r} #{index + 1}: "
                      f"{result.get('total_ms', result.get('error'))}", flush=True)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    stem = args.model.replace(":", "_").replace("/", "_")
    artifact = {"generated_at": datetime.now(timezone.utc).isoformat(),
                "model": args.model, "model_details": metadata,
                "orac_model_selection": "requested in meta.model; verify selected model in server logs",
                "direct_prompt": "minimal; not provider-bound Orac prompt",
                "rows": rows}
    (args.output_dir / f"{stem}.json").write_text(
        json.dumps(artifact, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    with (args.output_dir / f"{stem}.csv").open("w", newline="", encoding="utf-8") as stream:
        fields = ("source", "model_requested", "selected_model", "prompt", "iteration", "warmup",
                  "sent_ms", "ttft_ms", "stream_end_ms", "total_ms", "error",
                  "load_duration", "prompt_eval_duration", "eval_duration",
                  "total_duration", "prompt_eval_count", "eval_count")
        writer = csv.DictWriter(stream, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    """Parse benchmark options and run the latency matrix."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--ollama-url", default="http://127.0.0.1:11434")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--user", default=os.environ.get("USER", ""))
    parser.add_argument("--secret-file", type=Path, default=Path("/run/orac/slave.secret"))
    parser.add_argument("--include-orac", action="store_true")
    parser.add_argument("--orac-only", action="store_true")
    parser.add_argument("--repetitions", type=int, default=3)
    parser.add_argument("--warmups", type=int, default=1)
    parser.add_argument("--timeout", type=float, default=180)
    parser.add_argument("--num-predict", type=int, default=256)
    parser.add_argument("--keep-alive", default="30m")
    args = parser.parse_args()
    if args.repetitions < 1 or args.warmups < 0:
        parser.error("repetitions must be positive and warmups nonnegative")
    if args.orac_only:
        args.include_orac = True
    asyncio.run(run(args))


if __name__ == "__main__":
    main()
