
# Orac TODO Backlog

## Purpose

This backlog captures ideas and integration threads that should not be lost as Orac moves from core platform work into Home Assistant sync, speech, display, and satellite Raspberry Pi work.

## Near-Term Core Priorities

### 0. Processing Profile Execution

Priority: High

Status: Required follow-on after scoped dialogue retrieval

Purpose:

* Make persisted `processing_profile` and `processing_instruction` values alter
  extraction and chunking through versioned, Core-owned profile behaviour.
* Preserve raw-source provenance and deterministic replay.
* Treat profile and operator instructions as untrusted data, not executable
  prompts or plugin-owned code.

Explicit exclusions from the scoped dialogue first slice:

* No profile-driven extraction or chunking change.
* No model-generated transformation pipeline.
* No plugin access to protected `orac_core` objects.

Validation must cover profile version changes, retries, unchanged documents,
failed transformations, and current-version selection.

---

### 1. Home Assistant runtime sync

Priority: High

Status: Implemented for startup sync; periodic refresh/websocket follow-up pending

Value:

* Turns the deployed `orac_ha` schema into live shadow data.
* Allows Orac to resolve areas, devices, entities and states locally.
* Reduces reliance on live Home Assistant lookups during intent resolution.
* Provides the foundation for natural commands such as "turn on the lounge lights".

Completed:

* Database deployment is working.
* Database-side sync API is now in place.
* `HomeAssistantClient` fetches areas, devices, entities and states.
* `HomeAssistantSyncCoordinator` feeds payloads into
  `HomeAssistantRepository`.
* The managed `HomeAssistantService` runs startup sync inside the Orac-managed
  plugin service process.

Notes:

* Sync must run inside the Orac-managed plugin service process.
* Python must write via `HomeAssistantRepository` and `orac_ha.ha_sync_api`, not raw DML.

Next actions:

* Add periodic refresh or websocket state listener.
* Surface sync status through APEX and/or React.

---

### 2. Home Assistant intent resolution

Priority: High

Status: Partially implemented

Value:

* Converts synced HA shadow data into usable command resolution.
* Lets Orac map natural language to specific HA entities.
* Supports area-based commands such as "turn on the kitchen lights".
* Avoids using the LLM for every device lookup.

Notes:

* Should use shadow tables as the source of truth.
* Should support explicit entity names, areas, domains and aliases.
* LLM should assist with ambiguity, not own the core resolution path.
* Alias handling needs care: user-confirmed aliases should be trusted more than LLM-suggested ones.

Next actions:

* Define deterministic resolution rules.
* Add alias tables or confirm existing table design.
* Support room/area synonym handling, e.g. "lounge" -> "living room".
* Add fallback clarification when resolution is ambiguous.

---

### 3. Plugin service lifecycle hardening

Priority: High

Status: Implemented foundations; hardening ongoing

Value:

* Keeps long-running plugin services manageable.
* Prevents loose background processes from creeping in.
* Supports health checks, restart policy and clean shutdown.
* Required before satellite devices rely on always-on services.

Notes:

* `PluginServiceManager` already appears to have useful foundations.
* Need to ensure health-check intervals and failure thresholds are fully honoured.
* Home Assistant is the first real test of the service model.

Next actions:

* Confirm service health supervision is complete.
* Confirm restart policy behaviour under real failure.
* Ensure stop events are used rather than unmanaged sleeps.
* Surface plugin service status through APEX and/or React.
* Design a general versioned, idempotent plugin database migration mechanism.
  Home Assistant currently uses payload-local rerunnable DDL compatibility.

---

## Speech, Audio and Realtime Interaction

### 4. LiveKit integration

Priority: High

Status: POC groundwork in place

Value:

* Candidate for realtime audio sessions.
* May simplify satellite Raspberry Pi audio transport.
* Potentially useful for barge-in, turn handling and future multi-device sessions.
* Could avoid hand-rolling all realtime media/session plumbing.

Notes:

* LiveKit should remain optional until proven.
* Orac should still own intent routing, plugin execution and memory.
* LiveKit should be treated as a media/session layer, not the Orac brain.
* The key test is barge-in: user interrupts while Orac is speaking, and Orac stops cleanly.

Next actions:

* Build isolated LiveKit POC.
* Prove microphone -> STT -> Orac -> TTS -> playback.
* Test barge-in with real speaker/mic echo.
* Decide whether LiveKit becomes the preferred satellite transport.

---

### 5. Barge-in support

Priority: High

Status: Experimental implementation in place

Value:

* Makes voice interaction feel natural.
* Allows the user to interrupt Orac mid-response.
* Reduces frustration when Orac starts explaining too much.

Notes:

* Barge-in is separate from follow-up listening.
* Needs echo handling so Orac does not interrupt itself.
* LiveKit may help, but Orac still needs interruption policy.

Next actions:

* Define interruption behaviour.
* Stop or duck current TTS when interruption is accepted.
* Cancel or truncate the active response cleanly.
* Keep conversation history sane after interruption.

---

### 6. Follow-up listening window

Priority: Medium

Status: Partially implemented

Value:

* Avoids requiring the wake word for every follow-up.
* Allows natural short exchanges.
* Useful for commands like "make them brighter" after "turn on the lounge lights".

Notes:

* Suggested default: no more than 6 seconds.
* Shorter after simple command completion.
* Longer only when Orac explicitly asks a clarification question.
* Must not treat ordinary room conversation as a command.

Next actions:

* Add configurable follow-up timeout.
* Add state indicator: idle, listening, thinking, speaking, follow-up, muted.
* Add confidence gating for follow-up commands.

---

### 7. WakeLab / wake-word testing

Priority: Medium

Status: Needs retest

Correction:

* "wakewword" -> "wake word".

Value:

* Wake word quality determines whether Orac feels usable.
* Needs to work for both you and Nicola.
* False negatives will make Orac annoying.
* False positives will make Orac creepy.

Notes:

* The current wake word works for you.
* Nicola's voice still needs testing.
* Need to confirm whether "WakeLab" is the final tool name or just the working name.

Next actions:

* Test Nicola's wake-word detection.
* Test across rooms and distances.
* Test TV/background noise.
* Record false positives and false negatives.
* Decide whether to train/adapt separate profiles.

---

### 8. Speaker recognition / voice recognition

Priority: Medium

Status: Not started

Correction:

* Better term: speaker recognition or speaker identification.

Value:

* Allows Orac to select the correct user profile.
* Enables per-user preferences, voice, permissions, memory and context.
* Useful if Nicola and you use Orac differently.

Notes:

* This should not be confused with speech-to-text.
* STT answers "what was said".
* Speaker recognition answers "who said it".
* It should be confidence-based and able to fall back to "unknown user".

Next actions:

* Define user profile selection rules.
* Add "unknown speaker" behaviour.
* Decide whether recognition is local-only.
* Avoid allowing low-confidence speaker detection to authorise sensitive actions.

---

### 9. IndexTTS2 voice cloning / voice design

Priority: Medium

Status: Research / not started

Correction:

* Prefer "IndexTTS2" if that is the actual tool being used.
* Use "voice cloning" carefully; "voice design" or "custom voice generation" may be better for Orac.

Value:

* Could provide a more characterful Orac voice.
* May allow private/local voice generation.
* Useful if Piper or Kokoro voices feel too generic.

Notes:

* Should require explicit consent for any real person's voice.
* Should be optional, not a dependency for Orac v1.
* Piper/Kokoro should remain the reliable baseline.

Next actions:

* Confirm install/runtime requirements.
* Test quality and latency.
* Decide whether it can run on the current GPU/CPU budget.
* Integrate only behind the existing TTS provider abstraction.

---

### 10. TTS provider selection and fallback

Priority: Medium

Status: Implemented foundations; UI warning follow-up pending

Value:

* Lets Orac switch between Piper, Kokoro and future providers.
* Supports user preference driven voice selection.
* Makes failure modes more graceful.

Notes:

* We already discussed user preference driven voice selection.
* Need visible fallback warning if preferred voice/provider is unavailable.
* React display and APEX could both show voice/provider status.

Next actions:

* Confirm provider fallback status handling.
* Add UI warning/status line.
* Add tests for unavailable preferred voice.

---

## User Interfaces

### 11. APEX administration UI

Priority: High

Status: Planned

Correction:

* Do not forget APEX. It is a major part of Orac.

Value:

* Best place for database-backed configuration and admin.
* Good fit for plugin configuration, user preferences, logs and operational status.
* Strong fit for Home Assistant shadow table inspection.

Notes:

* APEX should remain the command centre/admin interface.
* React should not replace APEX for database-heavy admin work.

Next actions:

* Add HA sync status pages.
* Add plugin status pages.
* Add user preference pages for model, voice and perhaps wake/follow-up behaviour.
* Add operational dashboard for service health and recent errors.

---

### 12. React display UI

Priority: High

Status: Partially implemented

Value:

* Ideal for Pi mini display/kiosk use.
* Better than APEX for realtime local display.
* Can show Orac state: idle, listening, thinking, speaking, follow-up, muted.
* Can display model/voice fallback warnings.

Notes:

* Existing React UI under `web/orac-display` should be reused.
* Add satellite/kiosk mode rather than making every satellite a full console.

Next actions:

* Add compact satellite display route.
* Add status websocket/SSE feed.
* Add last transcript and last response display.
* Add error/warning status line.
* Support room/satellite identity display.

---

### 13. Small Pi display and physical satellite unit

Priority: Medium

Status: Planned

Value:

* Makes Orac visible and understandable.
* Allows users to see when Orac is listening or in follow-up mode.
* Makes a Pi satellite feel like an appliance, not a science project.

Notes:

* Ideal unit could combine:

  * Raspberry Pi 5
  * mic array
  * speaker
  * small display
  * optional touchscreen
  * 3D printed enclosure

Next actions:

* Decide screen size.
* Decide mic/speaker hardware.
* Build React kiosk mode.
* Look for or design a 3D printable enclosure.
* Keep the satellite thin: audio/display endpoint only.

---

## Memory, Embeddings and Knowledge

### 14. Conversation capture and embeddings

Priority: Medium

Status: Schema groundwork in place

Value:

* Lets Orac build long-term local memory.
* Allows previous conversations to supplement context.
* Useful for project knowledge, household preferences and recurring topics.

Notes:

* Needs careful privacy controls.
* Not every conversation should be stored permanently.
* The user should be able to save, forget, tag and review memories.
* Good candidate for Oracle-backed metadata plus vector embeddings.

Next actions:

* Define conversation capture policy.
* Add "save this conversation" workflow.
* Store transcript chunks with metadata.
* Generate embeddings.
* Add retrieval into Orac prompt/context pipeline.
* Add APEX review/delete UI.

---

### 15. Document uploads and embeddings

Priority: Medium

Status: Not started

Value:

* Lets Orac ingest PDFs, markdown, text, docs and other local files.
* Useful for project docs, manuals, household documents and technical references.
* Makes Orac a local knowledge system, not just a chatbot.

Notes:

* Previously discussed front doors included APEX upload, watched folders, email, Telegram and Hermes-style parcel handling.
* Start with one simple path before adding multiple ingestion routes.
* APEX upload is probably the cleanest first version.

Next actions:

* Define supported file types.
* Convert documents to markdown/text where practical.
* Chunk content.
* Store document metadata.
* Generate embeddings.
* Add retrieval/search UI.
* Add delete/reindex workflow.

---

### 16. Local vector/RAG layer

Priority: Medium

Status: Schema groundwork in place

Value:

* Supports conversation memory and document retrieval.
* Helps Orac answer from local project/home knowledge.
* Reduces dependence on model context alone.

Notes:

* Needs a clear boundary between factual retrieval and LLM generation.
* Retrieval should provide citations/source references internally.
* Should support project-specific and user-specific scopes.

Next actions:

* Decide embedding model.
* Decide storage approach.
* Add retrieval API.
* Add ranking and context-injection rules.
* Add source display in React/APEX where useful.

---

## External Interfaces and Agent Integrations

### 17. Open WebUI integration

Priority: Medium

Status: Not started

Value:

* Useful as a daily-driver chat/workspace interface.
* Could act as a front-end into Orac.
* Can support manual knowledge capture workflows.

Notes:

* Open WebUI should be an interface, not the Orac core.
* Orac remains the durable local knowledge and plugin platform.
* Integration should not compromise Orac's local-first design.

Next actions:

* Define what Open WebUI sends to Orac.
* Add "save to Orac" workflow if practical.
* Decide whether Orac appears as a model/backend/tool.
* Keep integration optional.

---

### 18. Hermes Agent integration

Priority: Low

Status: Parked

Correction:

* "Hemes Agaent" -> "Hermes Agent".

Value:

* Could handle longer-running agentic tasks.
* Could act as a "parcel manager" for email, uploads or external workflows.
* Could be useful for delegated research or automation.

Notes:

* Low priority.
* It must justify its complexity.
* It should not become the primary Orac voice layer.
* If integrated, the UI should clearly distinguish Orac responses from Hermes responses.

Next actions:

* Park until core Orac is stable.
* Revisit after Open WebUI and memory ingestion are clearer.
* Define one compelling use case before adding it.

---

### 19. MCP/tool server integration

Priority: Low to Medium

Status: Not started

Value:

* Could expose Orac actions to compatible tooling.
* Could allow standardised tool calls into Orac plugins or knowledge stores.
* Useful if Orac becomes a broader local automation hub.

Notes:

* Not urgent.
* Should wait until plugin/runtime contracts settle.
* Avoid building a second plugin system by accident.

Next actions:

* Keep as architecture note.
* Revisit after Home Assistant and memory/RAG are stable.

---

### 20. n8n/webhook integration

Priority: Low

Status: Parked

Value:

* Useful for event-driven automations.
* Could trigger Orac ingestion or plugin actions from external systems.
* Good for glue workflows.

Notes:

* Optional.
* Not needed for Orac voice assistant v1.
* Could be useful later for household or document-ingestion flows.

Next actions:

* Park.
* Revisit when Orac has stable APIs and auth boundaries.

---

## Runtime, Models and Infrastructure

### 21. Ollama / llama.cpp control plane

Priority: Medium

Status: Partially implemented

Value:

* Gives Orac direct model lifecycle control.
* Avoids depending only on LM Studio.
* Supports model availability, fallback and user preferences.

Notes:

* You have already moved strongly towards Ollama.
* qwen3.6 48K is currently the practical default for the 16 GB RTX 5060 Ti setup.
* Need clean model registration and enablement.

Next actions:

* Finalise model registry.
* Add enabled_yn / selectable flag.
* Show fallback warnings in UI.
* Add start/restart model handling through `orac-ctl.sh`.

---

### 22. Model fallback visibility

Priority: Medium

Status: Partially implemented

Value:

* Prevents silent degradation.
* Lets the user see when Orac is using a fallback model.
* Important for trust when a preferred model is unavailable.

Notes:

* We discussed an amber warning next to the model name.
* Also useful in the React display status line.

Next actions:

* Add fallback status to runtime state.
* Display in React.
* Display in APEX admin/status pages.

---

### 23. Docker Compose / service estate rationalisation

Priority: Medium

Status: Partially implemented

Value:

* Reduces container sprawl.
* Makes Orac easier to start, backup and maintain.
* Useful as optional services grow: Kokoro, search, Open WebUI, Hermes, display, LiveKit.

Notes:

* Desired direction discussed: compose stacks and profiles.
* Candidate profiles:

  * voice
  * search
  * ui
  * dev
  * agents

Next actions:

* Consolidate current Docker scripts.
* Define core vs optional services.
* Add profile-based startup.
* Keep backup/restore aligned with deployed services.

---

### 24. Backup, restore and migration hardening

Priority: Medium

Status: Partially implemented

Value:

* Protects Orac state as it becomes more valuable.
* Especially important once conversations, documents and embeddings are stored.
* Already proved useful with database export/import work.

Notes:

* Backup should include plugin schemas where configured.
* Document and embedding stores must be included once added.
* Need restore tests after schema/plugin changes.

Next actions:

* Add plugin schema backup coverage.
* Add restore validation.
* Add version compatibility checks.
* Include uploaded documents and vector data later.

---

## Search and External Knowledge

### 25. Internet/search integration

Priority: Medium

Status: Partially implemented

Value:

* Helps Orac avoid hallucinating current facts.
* Useful for factual answers, product questions and recent events.
* Already exposed issues where smaller models invented answers.

Notes:

* Search should be used more often for current, niche or factual claims.
* Needs result grounding and source handling.
* Should not blindly trust search snippets.

Next actions:

* Define search trigger policy.
* Add source citation/summary behaviour.
* Add search result caching where appropriate.
* Consider local SearXNG as an optional service.

---

### 26. SearXNG/local search service

Priority: Low to Medium

Status: Partially implemented

Value:

* Local/private metasearch option.
* Fits the local-first Orac philosophy.
* Could support Orac's internet-search core without tying it to one provider.

Notes:

* Optional service candidate.
* Could live behind a search provider abstraction.

Next actions:

* Park until core search policy is stable.
* Add as Docker Compose optional profile later.

---

## Security, Privacy and Control

### 27. Plugin permissions and entitlements

Priority: High

Status: Partially implemented

Value:

* Keeps plugins from becoming uncontrolled privileged code.
* Supports safer future plugin expansion.
* Important for Home Assistant, database writes and network access.

Notes:

* Existing manifest entitlements are a good foundation.
* Need runtime enforcement, not just declaration.
* Database access should remain through `ORAC_PLUGIN`.

Next actions:

* Review entitlement enforcement.
* Confirm network entitlement checks.
* Confirm database session rules.
* Add APEX/plugin UI visibility for entitlements.

---

### 28. Personal data controls

Priority: High once memory starts

Status: Not started

Value:

* Essential for trust.
* Required before long-term conversation/document memory becomes serious.
* Lets users review and delete stored information.

Notes:

* Applies to conversations, embeddings, documents, speaker profiles and voice data.
* Should be easy to inspect from APEX.

Next actions:

* Add memory review UI.
* Add delete/forget workflows.
* Add retention controls.
* Mark sensitive records where appropriate.

---

## Possible Later Enhancements

### 29. Email ingestion

Priority: Low to Medium

Status: Parked

Value:

* Could allow Orac to ingest useful documents or notifications.
* Could support "parcel manager" workflows.

Notes:

* Previously discussed as possible Hermes/Open WebUI/agent adjacent work.
* Not needed for v1 voice assistant.

Next actions:

* Park.
* Revisit after document ingestion exists.

---

### 30. Watched folder ingestion

Priority: Low to Medium

Status: Parked

Value:

* Simple local-first route for adding documents.
* Avoids overcomplicating early ingestion with email or messaging apps.

Notes:

* Could be easier than Telegram/email first.
* Needs duplicate detection and reindexing.

Next actions:

* Consider after APEX upload path.
* Add file watcher only if needed.

---

### 31. APEX file upload ingestion

Priority: Medium

Status: Not started

Value:

* Cleanest first document ingestion path.
* Fits existing Oracle/APEX strengths.
* Easy to combine with metadata, review and delete screens.

Notes:

* Better first step than Telegram or email ingestion.
* Keeps security and visibility inside Orac.

Next actions:

* Add upload page.
* Add document metadata table.
* Add conversion/chunking job.
* Add embedding job.

---

### 32. Satellite Pi room identity

Priority: Medium

Status: Not started

Value:

* Lets commands like "turn the lights on" resolve to the satellite's room.
* Makes voice control feel much more natural.

Notes:

* Each satellite should have a configured `satellite_id`.
* Each satellite can provide a default area, e.g. kitchen or lounge.
* Server-side intent resolution should use this as context.

Next actions:

* Add satellite registry table.
* Add default area per satellite.
* Include satellite_id in audio/session messages.
* Surface room identity in React display.

---

### 33. Local mute/privacy controls

Priority: Medium

Status: Display-only groundwork in place

Value:

* Important for household acceptance.
* Lets people know when microphones are disabled.
* Prevents accidental listening during private moments.

Notes:

* Physical mute button would be ideal.
* React display should show muted state clearly.
* Server should treat muted satellites as unavailable for audio capture.

Next actions:

* Add mute state to satellite model.
* Add UI indicator.
* Consider hardware button support later.

---

## Suggested Priority Order

1. Finish Home Assistant runtime sync.
2. Add Home Assistant intent resolution from shadow tables.
3. Harden plugin service health/restart/shutdown.
4. Build LiveKit barge-in POC.
5. Stabilise wake word and follow-up mode.
6. Add React satellite/kiosk display mode.
7. Start Raspberry Pi satellite endpoint.
8. Add speaker recognition/user profile selection.
9. Add conversation/document memory with embeddings.
10. Add Open WebUI integration.
11. Revisit IndexTTS2 voice design.
12. Park Hermes Agent, MCP and n8n until Orac v1 is stable.

## Guiding Architecture

APEX:

* admin
* configuration
* user preferences
* plugin/database visibility
* logs and operational dashboards

React:

* realtime Orac display
* satellite/kiosk UI
* status, transcript, response and warning surface

Oracle Database:

* durable state
* plugin schemas
* shadow tables
* memory/document metadata
* sync logs
* audit/history

Orac Python runtime:

* plugin manager
* service manager
* LLM routing
* STT/TTS
* Home Assistant sync
* intent resolution
* local model control

Satellite Pi:

* thin audio endpoint
* optional display
* room identity
* heartbeat/status
* no local LLM
* no local plugin logic
