<p align="center">
  <img src="./assets/images/OracLogo.png" alt="Orac Logo" width="300">
</p>

<h1 align="center">Orac - Version 0.1.0</h1>

<p align="center">
  <em>Your retro-futuristic home AI assistant.</em>
</p>

<p align="center">
  <a href="https://github.com/Avalon60/orac">
    <img src="https://img.shields.io/badge/python-3.9%2B-blue.svg" alt="Python 3.9+">
  </a>
  <a href="LICENSE">
    <img src="https://img.shields.io/badge/license-MIT-green.svg" alt="License">
  </a>
  <a href="https://github.com/Avalon60/orac/actions">
    <img src="https://img.shields.io/github/actions/workflow/status/Avalon60/orac/ci.yml?branch=main&label=build" alt="Build Status">
  </a>
</p>

---

## ✨ Features (currently a roadmap)

- 🎤 **Voice-Driven AI**: Natural language interaction via satellite Raspberry Pi units.  
- 🧠 **Conversational Intelligence**: Integrated with LM Studio for cutting-edge AI responses.  
- 🏠 **Smart Hub Control**: Manage lights, media, and IoT devices seamlessly.  
- 🧩 **Home Assistant Integrations**: Works hand-in-hand with Home Assistant for extensive smart home control.  
- 💬 **Client Chatbot**: Interact with Orac through a web or desktop chatbot interface.  
- 🌐 **Supports Multiple LLM Services**: Connects to LM Studio, Ollama, OpenAI, and more.  
- 🛠 **Modular Design**: Easily extend Orac with custom skills and automations.  
- 🐧 **Linux Server Deployment**: The supported Orac server deployment path is Linux-based.  
- 🔑 **Administered via APEX Web Console**: User and configuration management through Oracle APEX at [http://localhost:8042/ords/orac/f?p=1042:LOGIN](http://localhost:8042/ords/orac/f?p=1042:LOGIN).  

---

## 📂 Quick Links

- [Installation](#-installation)
- [Prerequisites](#-prerequisites)
- [Oracle Free Setup](#-oracle-free-setup)
- [APEX Administration](#-apex-administration)
- [Usage](#-usage)
- [License](#-license)

---

## 📦 Installation

Clone the repository and install Orac in editable mode on the Linux machine that will host the Orac server:

```bash
git clone https://github.com/Avalon60/orac.git
cd orac
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

The database deployment scripts expect to run from a Linux host with `bash`, `sudo`, and Docker available.

---

## 📋 Prerequisites

The current local-database deployment path is implemented by `bin/orac-db-deploy.sh`. That script assumes:

- A Linux host for the Orac server runtime.
- Docker Engine is installed.
- The Docker daemon is running.
- Docker Buildx is available, because the script builds the database image with `docker buildx bake`.
- `sudo` access is available, because the script creates and fixes ownership on the host persistence directory.
- Python 3.9+ is installed for the Orac utilities.
- A local checkout of this repository exists on the target machine.

The deployment script currently supports only:

- `TOPOLOGY=db-local`

If you are using a remote Oracle database topology, `bin/orac-db-deploy.sh` is not the correct setup path.

---

## 🛢 Oracle Free Setup

Orac uses an Oracle Database container for local configuration and metadata storage. The supported local setup path is:

1. Configure `resources/config/orac.env`.
2. Prepare a host directory for persistent Oracle data files.
3. Create or confirm the `orac` database credential entry.
4. Run `bin/orac-db-deploy.sh` to build and start the database container.

### Configure `resources/config/orac.env`

`bin/orac-db-deploy.sh` sources `resources/config/orac.env` before doing any work. At minimum, review these settings:

```bash
export CONTAINER_NAME=orac-db
export ORADATA_DIR=/u01/orac-db/oradata
export ORAC_IMAGE_NAME=orac
export ORAC_IMAGE_TAG=latest
export PORT_SQLNET=1521
export PORT_HTTP=8042
export PORT_EM=5500
export TOPOLOGY=db-local
```

Important points:

- `TOPOLOGY` must remain `db-local` for this script.
- `ORADATA_DIR` is the host directory mounted into the container at `/opt/oracle/oradata`.
- `PORT_HTTP` defaults to `8042` on the host, even though the container listens on `8080`.

### Prepare the persistent database location

By default, the database files persist under:

```bash
/u01/orac-db/oradata
```

You can change that location by editing `ORADATA_DIR` in `resources/config/orac.env`.

The deployment script will:

- Create the directory if it does not already exist.
- Run `sudo chown -R 54321:54321 "${ORADATA_DIR}"` so the Oracle container user can write to it.

On a clean machine, prepare the parent location before running the deploy script if your environment requires it. For example:

```bash
sudo mkdir -p /u01/orac-db/oradata
sudo chown -R 54321:54321 /u01/orac-db/oradata
```

Choose a location with enough free space for Oracle data files and one that you intend to keep across container rebuilds. If you delete the contents of `ORADATA_DIR`, the database state is lost.

### Configure Database Credentials

Orac stores database connection credentials securely using the `dbconn-mgr.sh` utility. Credentials are encrypted and stored in `~/.Orac/dsn_credentials.ini`.

**Required credential:** `orac`

Run the following command to create the database connection:

```bash
bin/dbconn-mgr.sh -c orac
```

You will be prompted for:
- **Username**: `ORAC`
- **Password**: Choose a password (this will be used for both `ORAC` and `ORAC_PLUGIN` database users)
- **DSN**: The database connection string (e.g., `localhost:1521/FREEPDB1`)
- **Wallet ZIP path**: Optional, press Enter to skip if not using Oracle wallet

> ⚠️ The password you enter here is used by the container setup scripts to create the `ORAC` and `ORAC_PLUGIN` database users automatically.

To list configured connections:
```bash
bin/dbconn-mgr.sh -l
```

To edit an existing connection:
```bash
bin/dbconn-mgr.sh -e orac
```

### Configure Local Wake Word Activation

Local voice wake-word support uses openWakeWord as the recommended production
backend. It runs locally, does not require a vendor account, and processes
microphone PCM frames directly rather than using STT transcription.

Install the optional openWakeWord wake packages:

```bash
poetry install --no-root -E voice-wake-openwakeword
```

On Linux, microphone capture uses the existing `sounddevice` dependency and
may require system PortAudio packages such as `portaudio19-dev`.

The default development configuration uses the built-in `hey_jarvis` model to
prove the integration:

```ini
[voice]
activation_mode = openwakeword
wake_engine = openwakeword
openwakeword_model_names = hey_jarvis
openwakeword_threshold = 0.75
openwakeword_inference_framework = auto
wake_rearm_seconds = 1.0
console_timestamps = true
openwakeword_refractory_seconds = 2.0
```

To use a future custom Hey Orac model, place the model under the runtime tree
and configure its path:

```ini
[voice]
activation_mode = openwakeword
wake_engine = openwakeword
openwakeword_model_paths = ${ORAC_HOME}/var/models/wake/hey_orac.tflite
openwakeword_model_names =
```

Piper voice models follow the same runtime-tree convention. By default Orac
looks for Piper voices under:

```ini
[voice]
tts_engine = piper
tts_voice_dir = ${ORAC_HOME}/var/voices/piper
```

Put the Piper voice assets in that directory, or override `tts_voice_dir` if
you keep voices elsewhere.

Kokoro can be used as a higher-quality optional TTS backend when a local
Kokoro-FastAPI or compatible OpenAI speech API service is running. Orac does
not bundle Kokoro and does not require it for normal operation; install and
start the Kokoro speech server separately, then point Orac at its local HTTP
endpoint. The service must expose an OpenAI-compatible speech route and return
WAV audio.

The tested integration target is
[remsky/Kokoro-FastAPI](https://github.com/remsky/Kokoro-FastAPI), which
provides Docker images and a local OpenAI-compatible speech API. Follow the
upstream project for current installation details. A minimal local CPU start
using the published container image is:

```bash
docker run -p 8880:8880 ghcr.io/remsky/kokoro-fastapi-cpu:latest
```

For NVIDIA GPU support, use the upstream GPU image instead:

```bash
docker run --gpus all -p 8880:8880 ghcr.io/remsky/kokoro-fastapi-gpu:latest
```

The upstream project also supports Docker Compose and direct `uv` startup.
Use those paths if you want a pinned checkout, local UI, custom model storage,
or non-Docker development.

After starting Kokoro-FastAPI, verify the endpoint from another terminal:

```bash
curl -sS \
  -H 'Content-Type: application/json' \
  -o /tmp/orac-kokoro-test.wav \
  -X POST http://127.0.0.1:8880/v1/audio/speech \
  -d '{
    "model": "kokoro",
    "voice": "af_heart",
    "input": "Kokoro is available for Orac.",
    "response_format": "wav"
  }'
file /tmp/orac-kokoro-test.wav
```

The `file` command should report a WAV/RIFF audio file. If the curl command
fails, fix the Kokoro service before enabling `tts_engine = kokoro` in Orac.

Example Kokoro configuration:

```ini
[voice]
tts_engine = kokoro
tts_fallback_engine = piper
tts_kokoro_base_url = http://127.0.0.1:8880/v1
tts_kokoro_model = kokoro
tts_kokoro_voice = af_heart
tts_kokoro_response_format = wav
tts_kokoro_timeout_seconds = 60
tts_kokoro_api_key_env =
```

Kokoro-FastAPI supports weighted voice blends. Orac passes the configured
voice string through unchanged, so blends can be configured like this:

```ini
[voice]
tts_kokoro_voice = af_bella(2)+af_heart(1)
```

`tts_kokoro_base_url` may be configured with or without `/v1`, and with or
without a trailing slash. These forms are equivalent:

```ini
tts_kokoro_base_url = http://127.0.0.1:8880
tts_kokoro_base_url = http://127.0.0.1:8880/
tts_kokoro_base_url = http://127.0.0.1:8880/v1
tts_kokoro_base_url = http://127.0.0.1:8880/v1/
```

All resolve internally to:

```text
http://127.0.0.1:8880/v1/audio/speech
```

Use `tts_kokoro_voice` to select the Kokoro voice. Leave
`tts_fallback_engine = piper` if Piper should speak a chunk when Kokoro is
unavailable or returns an error. Set `tts_engine = piper` to return to the
lightweight local backend.

Run a local wake-word smoke test with:

```bash
PYTHONPATH=src poetry run python -m orac_voice.voice_loop_local --voice-session --activation-mode openwakeword
```

Set `activation_mode = enter` to disable wake-word detection and keep the
manual press-Enter flow.

If Orac hears its own spoken response and immediately wakes again, increase
`wake_rearm_seconds`, `openwakeword_refractory_seconds`, or
`openwakeword_threshold`. The `hey_jarvis` model is a proof model, not a
trained Hey Orac model, so some false activation is expected until a real Orac
wake model is supplied.

Local voice sessions also support a first-pass barge-in mode. The server emits
explicit `tts_playback_started`, `tts_playback_finished`,
`tts_playback_cancelled`, and `tts_playback_error` events from the TTS worker.
The voice client starts its barge-in monitor only after playback starts and
stops it when playback finishes, is cancelled, or fails. The recommended mode
is `openwakeword`, which requires the wake word again during TTS playback
before it sends a voice-cancel request to the Orac server. This avoids Orac
cancelling itself just because the microphone can hear the speaker output.

```ini
[voice]
barge_in_enabled = false
barge_in_mode = openwakeword
barge_in_min_speech_ms = 250
barge_in_grace_ms = 500
barge_in_cooldown_ms = 1000
barge_in_return_mode = wake_listening
barge_in_ignore_during_tts_start_ms = 300
barge_in_post_response_ms = 12000
barge_in_post_response_cancel_enabled = false
```

Set `barge_in_enabled = true` only when testing barge-in. Use
`barge_in_return_mode = wake_listening` when interruption should stop Orac
and then wait for the wake word again. `command_capture` remains available for
immediately recording a replacement command after interruption, but it is more
sensitive to microphone/speaker timing.
`barge_in_post_response_cancel_enabled` remains disabled by default; playback
lifecycle events, not post-response timers, are the normal source of truth for
when barge-in is active.

`barge_in_mode = vad` remains available as a diagnostic mode, but it does not
perform acoustic echo cancellation. If the microphone hears the speaker output,
VAD may falsely interrupt. Prefer `barge_in_mode = openwakeword`; if you must
test VAD-only barge-in, increase `barge_in_grace_ms`,
`barge_in_ignore_during_tts_start_ms`, or `barge_in_min_speech_ms`, raise the
normal `vad_speech_start_threshold`, lower speaker volume, or use
headphones/echo-cancelling input hardware.

`stt_phrase` remains available as a diagnostic fallback, but it is not a
production wake-word detector because it records and transcribes each candidate
phrase before activation.

Porcupine remains optional/vendor-gated. It requires Picovoice credentials and
the Porcupine extra:

```bash
poetry install --no-root -E voice-wake-porcupine
PYTHONPATH=src poetry run python -m lib.api_key_store --set picovoice/access_key
```

Do not store the Picovoice AccessKey in `resources/config/orac.ini`; store it
encrypted in `~/.Orac/api_keys.ini`.

If the `orac` credential does not already exist, `bin/orac-db-deploy.sh` will attempt to initialize it for you by calling:

```bash
bin/dbconn-mgr.sh -c orac
```

### Build and start the Orac database container

Run:

```bash
bin/orac-db-deploy.sh
```

What the script does:

- Verifies that `resources/config/orac.env` exists.
- Verifies Docker is installed and the daemon is running.
- Ensures the persistent `ORADATA_DIR` exists and is owned by UID/GID `54321:54321`.
- Ensures the `orac` credential exists.
- Reads the Oracle password from the stored `orac` credential.
- Builds the local Orac database image with Docker Buildx.
- Starts the database container with these mappings:

```text
Host SQL*Net port  ${PORT_SQLNET} -> Container 1521
Host HTTP port     ${PORT_HTTP}   -> Container 8080
Host EM port       ${PORT_EM}     -> Container 5500
Host ORADATA_DIR   ${ORADATA_DIR} -> /opt/oracle/oradata
```

- Waits for the log marker `=  ORAC deployment complete =`.

Useful options:

```bash
bin/orac-db-deploy.sh --dry-run
bin/orac-db-deploy.sh --force
bin/orac-db-deploy.sh --force --no-cache
```

Notes:

- If a container with the configured name already exists, the script stops unless you pass `--force`.
- `--force` removes the existing container and deletes Oracle marker directories under `ORADATA_DIR` before rebuilding.
- The first build and deployment can take a significant amount of time. The script waits up to 30 minutes for completion.

Important:

- `bin/orac-db-deploy.sh` deploys the Oracle database container, ORDS/APEX, and the Orac database objects.
- At the end of that script, the database side is running, but the full Orac stack is not yet up.
- The Orac AI engine is a separate host process and must be started afterward.

### What constitutes the Orac stack

For operational purposes, the Orac stack consists of:

- the Oracle database container
- ORDS / APEX served from that container
- the Orac AI engine running on the Linux host

`bin/orac-db-deploy.sh` only handles the first two items plus schema/app deployment. It does not start the AI engine.

### Start the full Orac stack after database deployment

After `bin/orac-db-deploy.sh` completes successfully, start the full stack with:

```bash
bin/orac-ctl.sh start
```

Then confirm both halves are running:

```bash
bin/orac-ctl.sh status
```

If you only want to start the AI engine after the database is already running, you can use:

```bash
bin/orac.sh start
```

---

## 🧭 APEX Administration

Orac’s user-management and configuration functions are handled through the **Orac Admin APEX application**, which provides a browser-based interface for maintaining users, skills, and system settings.

Once your Oracle Free / ORDS stack is running, open the Orac Admin app in a browser:

```
http://localhost:8042/ords/f?p=1042:LOGIN
```

This URL launches the **Orac Administration Application** login page.

### Default Workspace and Credentials

| Setting       | Value                  | Notes                                                       |
| ------------- | ---------------------- | ----------------------------------------------------------- |
| **Workspace** | `ORAC`                 | APEX workspace associated with the Orac schema.             |
| **Username**  | `ORAC_ADMIN`           | The initial administrative account.                         |
| **Password**  | *(set on first login)* | You’ll be prompted to choose a password at initial sign-in. |

After first login, you can use the APEX interface to manage user accounts, roles, permissions, and configuration data.

> 💡 *This application provides everyday administration of Orac — including user setup, role management, and configuration — with no command-line access required.*

> 🧰 *Developers who need to access the underlying APEX workspace can still do so via:*
> [http://localhost:8042/ords/r/apex/workspace-sign-in/oracle-apex-sign-in](http://localhost:8042/ords/r/apex/workspace-sign-in/oracle-apex-sign-in)

> 🌍 *If accessing from another machine or container, replace `localhost` in the URL with your host’s IP address or hostname (e.g., `http://192.168.0.42:8042/ords/f?p=1042:LOGIN`).*

---

### 🧩 Troubleshooting APEX Login

If you cannot access the Orac Admin application:

1. **Verify ORDS is running:**
   Check your container logs or terminal output — you should see a line like:

   ```
   INFO  ORDS has started and is listening on port 8042
   ```

2. **Check the URL:**
   Ensure the URL path ends with `f?p=1042:LOGIN` (not the developer workspace path).

3. **Confirm port mapping (Docker):**
   If running in a container, make sure port **8042** on the host maps to **8042** in the container:

   ```bash
   docker ps
   ```

   Look for `0.0.0.0:8042->8042/tcp`.

4. **Clear browser cache or use incognito mode:**
   Cached session tokens sometimes prevent APEX login pages from loading correctly.

5. **Reset ORAC_ADMIN password (if forgotten):**
   Connect via SQL*Plus or SQLcl:

   ```sql
   ALTER USER ORAC_ADMIN IDENTIFIED BY new_password;
   ```

6. **Check APEX version / installation:**
   If the login page still fails to load, confirm that APEX is properly installed and configured in the PDB:

   ```sql
   SELECT version FROM apex_release;
   ```

> 🧠 *Tip: If the APEX listener doesn’t respond, restart the ORDS service or your container — it usually resolves transient startup timing issues.*

---

## 🛠 Usage

Use `bin/orac-ctl.sh` as the primary control script for the full Orac stack:

- Oracle database container
- ORDS / APEX HTTP endpoint
- Orac AI engine

Common commands:

```bash
bin/orac-ctl.sh start
bin/orac-ctl.sh stop
bin/orac-ctl.sh restart
bin/orac-ctl.sh status
bin/orac-ctl.sh logs
bin/orac-ctl.sh logs ai
bin/orac-ctl.sh logs db
```

What these do:

- `start`
  Starts the Oracle/ORDS container if needed, waits for the database, then starts the Orac AI engine.
- `stop`
  Stops the Orac AI engine, then stops the Oracle/ORDS container.
- `restart`
  Restarts the full stack.
- `status`
  Shows both container status and Orac AI engine status.
- `logs`
  Tails database / ORDS container logs by default.
- `logs ai`
  Shows Orac AI engine logs.
- `logs db`
  Shows database / ORDS container logs.

The lower-level `bin/orac.sh` script is still available if you only want to control the AI engine itself:

```bash
bin/orac.sh start
bin/orac.sh stop
bin/orac.sh status
bin/orac.sh logs
```

---

## Checking the Install
If `bin/orac-db-deploy.sh` does not complete successfully, inspect the database container logs:

`docker logs orac-db`

To monitor the deployment while it is still running:

`docker logs --tail 200 -f orac-db`

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

## 🤖 About the Name

The name **Orac** pays homage to the iconic AI from *Blake’s 7*—a nod to retro science fiction with modern AI innovation.

---

<p align="center">
  <em>"Logic is a wreath of pretty flowers which smell bad."</em>
</p>
