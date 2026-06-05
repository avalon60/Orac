# Home Assistant Plugin

This directory contains the runtime implementation for the `home_assistant` plugin.

Runtime configuration is loaded from `plugin.ini` in this directory. The file
may contain non-secret connection details such as host, port, protocol, and TLS
verification settings.

Do not store the Home Assistant token value in `plugin.ini`. Store the long-lived
access token in Orac's encrypted plugin PAT vault:

```bash
bin/plugin-pat-mgr.sh --plugin home_assistant --set access_token
```
