# Plugin Template

This directory is an illustrative starting point for a new Orac plugin implementation directory.

It is not a discoverable plugin by itself because there is no matching top-level manifest such as:

```text
plugins/_template.json
```

When creating a real plugin:

1. Create `plugins/<plugin-id>.json`
2. Create `plugins/<plugin-id>/`
3. Copy or adapt the files from this template as needed
4. Keep executable route metadata in the manifest, not in the implementation module
5. If deterministic dialogue matching is needed, declare `routing.interceptor`
   and add `plugins/<plugin-id>/resources/intercept_meta.json`

The current routing subsystem discovers plugins from manifests only and does not import plugin code for discovery or candidate retrieval.
Interception rules identify manifest routes by `route_id`; they do not duplicate
capability or intent strings.
