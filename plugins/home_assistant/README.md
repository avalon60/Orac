# Home Assistant Plugin

This directory contains the runtime implementation for the `home_assistant` plugin.

Runtime configuration is loaded from `plugin.ini` in this directory. The file
may contain connection details such as host, port, protocol, and the
`access_token_env` environment variable name.

Do not store the Home Assistant token value in `plugin.ini`; store only the
environment variable name that contains the token at runtime.
