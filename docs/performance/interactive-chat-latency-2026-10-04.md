# Interactive chat latency investigation — 4 October 2026

## State and method

The measured Orac bridge process (PID 1482211) was started before the source
changes in this investigation. The results below are one observation per cell,
not a verified before/after result. Orac requests used HMAC signed NDJSON,
fresh client identities to obtain distinct derived conversations, explicit
`meta.model`, and a terminal response timestamp. Server logs confirmed the
selected model for all four isolated requests. Direct Ollama requests used a
minimal two-message prompt (`you are orac.` plus the user turn),
`num_predict=256`, `think=false`, and `keep_alive=30m`. They are a provider
reference, not a prompt-equivalent comparison.

Commands (from the repository root):

```bash
.venv/bin/python bin/benchmark-chat-latency.py --model llama3.1-64K:latest --output-dir /tmp/orac-latency-20261004 --repetitions 1 --warmups 0 --timeout 120
.venv/bin/python bin/benchmark-chat-latency.py --model gpt-oss-64K:latest --output-dir /tmp/orac-latency-20261004 --repetitions 1 --warmups 0 --timeout 180
.venv/bin/python bin/benchmark-chat-latency.py --model llama3.1-64K:latest --output-dir /tmp/orac-latency-isolated-20261004 --repetitions 1 --warmups 0 --timeout 180 --orac-only
.venv/bin/python bin/benchmark-chat-latency.py --model gpt-oss-64K:latest --output-dir /tmp/orac-latency-isolated-20261004 --repetitions 1 --warmups 0 --timeout 180 --orac-only
```

Raw JSON and CSV are in the two `/tmp` directories named above. The first
bridge pass at `/tmp/orac-latency-live-20261004` was discarded: its client was
`slave`, so Orac ignored the arbitrary external session ID and reused the
user/client conversation. It also selected the user's Llama preference despite
the direct benchmark argument naming GPT OSS. The corrected tool varies the
client identity and requests the model explicitly.

## Observations

Times are milliseconds. TTFT is the first nonempty direct Ollama content
chunk or first Orac `text_delta`; total is the direct completion or Orac
terminal response. Cold/warm labels refer only to the direct samples' model
load duration, since residency was not controlled by unloading models.

| Model | Prompt | Direct TTFT | Direct total | Direct load | Orac first delta | Orac total |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| Llama 3.1 64K | Hi | 5,918 | 14,480 | 5,381 | 21,719 | 21,720 |
| Llama 3.1 64K | Python context managers | 433 | 26,100 | 2 | 53,787 | 53,795 |
| GPT OSS 64K | Hi | 26,320 | 29,240 | 9,081 | 61,749 | 61,749 |
| GPT OSS 64K | Python context managers | 5,973 | 22,217 | 2 | 61,216 | 61,225 |

Installed model digests from `/api/tags`:

- `llama3.1-64K:latest`: `2ce31acfcbd99a6384e5adbe95dd9e4f42838e1f8e76dcde40942cb032403c08`
- `gpt-oss-64K:latest`: `03e40f9916dfd9effeb2ca11b4598a889fc66560c07072dd32ce26e0fa8ac546`

The direct provider reported 21–85 prompt tokens for Llama and 76–85 for GPT
OSS. The current Orac log reported a safe input estimate of about 5,081 tokens
for one normal turn, so prompt size is a plausible contributor; these two
prompt shapes are not equivalent, and their time difference is not a measured
Orac overhead. Direct output reached the 256-token cap for the GPT OSS normal
prompt, which also limits comparability. In every measured bridge sample, the
first `text_delta` arrived within 9 ms of `stream_end`; user-visible streaming
was effectively absent in these observations. The source path has a native
streaming implementation and tests, so this needs a fresh-process trace to
distinguish buffering from model or routing behavior.

## Changes and verification status

The source change adds monotonic correlated phase summaries, Ollama duration
capture, a social-turn filter for optional retrieval, fixed-prompt reduction,
configurable keep-alive, and a durable scheduled title request worker. Title
generation is enqueued after assistant persistence and no longer invokes an
LLM in the response path. Focused tests cover context history, connector,
communications, client, and title worker paths.

The title SQL follows `install.sql → productController.xml → orac_core →
orac_api → orac_code → orac` through existing `includeAll` controllers. All
19 new title SQL files were staged into the local development container with
matching SHA256 hashes, and `deploy-orac-db.sh --validate` passed. The
`--update-sql` preview included unrelated `post_install` recompiles, reference
LOV views, and validation changesets in addition to title changesets. Database
update was therefore withheld; the live database has no title API objects.
The SQL is staged in the container but has not been applied.

No controlled cold-unload test, three-run warm median/min/max matrix, exact
provider-bound prompt comparison, post-change bridge deployment, or database
state validation was completed. The results cannot establish a material
improvement yet. A valid follow-up measurement requires deploying the scoped
database changes, restarting Orac with the edited source, confirming the
selected model and phase log for each request, then running warm-up plus at
least three measured repetitions per model/prompt. Compare exact effective
generation options and provider-bound prompt before attributing time to Orac.
