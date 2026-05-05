Backlog: LLM provider/config redesign

- Separate local-discovered models from cloud-configured models.
- Keep api_keys.ini under ~/.Orac for encrypted API keys.
- Distinguish inbound keys from outbound keys.
- Move user preferences towards selecting llm_config rather than raw llm_registry rows.
- Consider OraTAPI-style runtime profiles later.
- Add OpenAI-compatible gateway as optional first-party runtime later.



Possibly:

We need to add a new Orac API key credential manager named `keys_mgr.py`.

Context:
Orac already has a credential manager pattern for database DSN credentials, using files such as:

  ~/.Orac/dsn_credentials.ini

These credential files are not stored under `ORAC_HOME/resources/config`. They live under the user's home directory in:

  ~/.Orac/

Credential values are encrypted automatically for storage and decrypted on retrieval. The existing mechanism uses the machine ID as the encryption key, so the process is transparent on the same machine.

Please inspect the existing credential manager implementation, especially `dbconn_mgr.py`, `dbconn.py`, or any related encryption/config helper modules, and loosely base this new utility on the same conventions.

Goal:
Create a new command-line utility:

  keys_mgr.py

Its job is to maintain encrypted API keys in:

  ~/.Orac/api_keys.ini

Do not use `~/.Orac/keys.ini`.
Do not store API keys under `ORAC_HOME/resources/config`.

Concepts:
The key store must distinguish between:

1. inbound keys

   These are keys used by external clients calling Orac.

   Example:
   - Open WebUI calling Orac through an OpenAI-compatible gateway.

2. outbound keys

   These are keys Orac uses when calling external providers.

   Examples:
   - OpenAI
   - Google Gemini
   - Anthropic
   - Ollama cloud, if required later

Section naming:
Use the following section naming convention:

  [inbound.<name>]
  [outbound.<name>]

Examples:

  [inbound.orac.openai_gateway]
  enabled = true
  api_key = <encrypted_key>
  description = Key used by OpenAI-compatible clients calling Orac

  [outbound.llm_provider.openai]
  enabled = true
  api_key = <encrypted_key>
  description = Key used by Orac when calling OpenAI

  [outbound.llm_provider.google]
  enabled = true
  api_key = <encrypted_key>
  description = Key used by Orac when calling Google Gemini

  [outbound.llm_provider.anthropic]
  enabled = true
  api_key = <encrypted_key>
  description = Key used by Orac when calling Anthropic Claude

Important design boundary:
`api_keys.ini` should store encrypted API keys and directly related metadata only.

Do not turn `api_keys.ini` into a general runtime configuration file.

Do not store gateway listener settings such as:

  host
  port
  require_api_key
  base_url

These belong elsewhere, for example in `orac.ini`, `llm_registry`, or `llm_config`.

For example, `orac.ini` may later contain something like:

  [openai_gateway]
  enabled = true
  host = 127.0.0.1
  port = 11435
  require_api_key = true
  inbound_key_ref = orac.openai_gateway

The gateway would then resolve:

  direction = inbound
  name      = orac.openai_gateway
  section   = inbound.orac.openai_gateway
  store     = ~/.Orac/api_keys.ini

Command-line requirements:
Use `argparse`.

The tool should support these mutually exclusive operations:

  --create
  --edit
  --delete
  --list
  --show
  --get

Required options:

  --direction inbound|outbound

Required for create, edit, delete, show, and get:

  --name <name>

Optional:

  --description <description>
  --enabled true|false

Security behaviour:
- Prompt securely for API keys using `getpass.getpass()` unless a safe existing project convention already exists.
- Never echo plain text API keys during create or edit.
- Store API keys encrypted at rest using the existing Orac credential encryption mechanism.
- Decrypt only when retrieval is explicitly requested.
- `--list` must never reveal decrypted API keys.
- `--show` must redact API keys by default.
- `--get` should print the decrypted key only when `--reveal` is supplied.
- Without `--reveal`, `--get` should refuse to print the decrypted key or should print a redacted value only.
- Fail clearly if the key store was created on another machine and cannot be decrypted.
- Create `~/.Orac` if it does not exist.
- Set sensible local file permissions for the key store where possible.

Suggested CLI examples:

  python keys_mgr.py --list

  python keys_mgr.py --create \
    --direction inbound \
    --name orac.openai_gateway \
    --description "Key used by OpenAI-compatible clients calling Orac"

  python keys_mgr.py --create \
    --direction outbound \
    --name llm_provider.openai \
    --description "Key used by Orac when calling OpenAI"

  python keys_mgr.py --edit \
    --direction outbound \
    --name llm_provider.openai

  python keys_mgr.py --delete \
    --direction inbound \
    --name orac.openai_gateway

  python keys_mgr.py --show \
    --direction outbound \
    --name llm_provider.openai

  python keys_mgr.py --get \
    --direction outbound \
    --name llm_provider.openai \
    --reveal

Validation:
- Validate `--direction` as either `inbound` or `outbound`.
- Validate `--name`.
- Prevent users from accidentally passing names that already include `inbound.` or `outbound.`.
- The final section name should be constructed internally from direction and name.
- Prevent duplicate sections on create.
- Give a clear error if attempting to edit, delete, show, or get a missing section.
- Keep boolean values serialised consistently as `true` or `false`.

Implementation style:
- Python script.
- Include this header immediately after the shebang:

  # Author: Clive Bostock
  # Date: 2026-05-04
  # Description: Maintains encrypted inbound and outbound API keys for Orac.

- Use type hints.
- Use Google-style docstrings.
- Use `argparse` for command-line parameters.
- Use 2-space indentation.
- Keep functions small and testable.
- Reuse existing Orac helper modules where practical rather than duplicating encryption logic.
- Avoid broad exception swallowing.
- Print clear user-facing messages to stderr for errors.
- Exit with non-zero status on failure.
- Avoid logging decrypted secrets.

Deliverables:
1. Add `keys_mgr.py`.
2. Reuse or minimally extend the existing credential encryption utilities if needed.
3. Add any small helper functions required for:
   - resolving `~/.Orac/api_keys.ini`
   - loading/saving the INI file
   - constructing section names
   - encrypting/decrypting API keys
   - redacting displayed keys
4. Add basic tests if the project already has a test framework.
5. Update any relevant README or developer notes if there is an obvious place for this utility.

Out of scope for this task:
- Do not implement the OpenAI gateway yet.
- Do not change `orac.ini` loading unless there is already a natural place to document future integration.
- Do not add provider base URLs to `api_keys.ini`.
- Do not modify `llm_registry` or `llm_config`.
- Do not expose decrypted keys through logs.
