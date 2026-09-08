# Governed Retrieval Provider-Message Composition Follow-up

Status: architectural follow-up; not part of the focused required-retrieval
remediation.

## Confirmed Finding

The governed instructions, rendered ORAC_CORE offer, opaque handles, and native
`retrieve` schema reached Ollama. The production failure was not a Qwen tool
capability failure. It occurred when Orac flattened heterogeneous system policy,
session context, projected history, and ordinary-answer instructions into one
large provider-level `user` message used for the tool decision.

The captured production prompt was 13,569 characters with SHA-256
`57dfd93eecf5509f72039f99f2fdee78f544fdd62087bcdc874dd0bd7d4302ae`.
The provider message roles were `system`, `system`, `user`, with content lengths
731, 703, and 13,569 characters. The native schema offered exactly one
`retrieve` function with `query` and an opaque-handle-enumerated `domains`
array.

## Sanitised Replay Evidence

All replays used `qwen3.6-48K:latest` against the same local Ollama runtime and
the same governed schema.

| Framing | Tool calls |
| --- | ---: |
| Complete production framing | 0 |
| Complete production framing with projected history removed | 0 |
| Current request only | 1 valid `retrieve` call |
| Captured history plus current request | 1 valid `retrieve` call |
| Synthetic repeated prior assistant claims plus current request | 1 valid `retrieve` call |
| Production wrapper without its final directive | 1 valid `retrieve` call |
| Current request plus the final directive | 1 valid `retrieve` call |

No isolated history segment or final directive reproduced the failure. The
complete flattened wrapper materially changed instruction-following behaviour.
The focused remediation therefore uses compact provider messages for required
tool selection and retains the full prompt only for the grounded answer.

## Follow-up Boundary

Review whether the ordinary dialogue path should preserve provider-native
system, history, context, and current-user roles instead of serialising them
inside one outer `user` message. Any future change must preserve context
budgeting, plugin/context mediation, prompt-dump semantics, persistence,
authorisation, and provider compatibility. Do not couple that broader review to
the required-retrieval remediation or introduce a parallel prompt path without
an explicit architecture decision and replay coverage.
