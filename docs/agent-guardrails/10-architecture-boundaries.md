# Architecture Boundaries

## Non-negotiables

- Orac core owns orchestration, routing, persistence, and security boundaries.
- Plugins extend Orac; they do not redefine Orac.
- Plugin code must not bypass Orac core APIs to access protected core state.
- LLMs must not generate arbitrary SQL, shell commands, or privileged operations at runtime.
- Home Assistant integration must remain optional unless explicitly required by a feature.
- The content engine is on the critical path and must remain the central mediation layer for conversational context.
