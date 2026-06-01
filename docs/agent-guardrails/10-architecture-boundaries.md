# Architecture Boundaries

## Non-negotiables

- The core runtime owns orchestration, routing, persistence, and security boundaries.
- Plugins extend the platform; they do not redefine it.
- Plugin code must not bypass approved APIs to access protected state.
- LLM-mediated SQL, shell, and privileged operations must remain within validated, policy-constrained execution paths.
- Integration-specific capabilities must remain optional unless explicitly required by a feature.
- Where conversational or AI context is part of the architecture, its mediation layer must not be bypassed, and its control path must be explicitly documented.
