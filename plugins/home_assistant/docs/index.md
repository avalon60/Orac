# Home Assistant Plugin

The Home Assistant plugin treats Home Assistant as the hardware and integration
abstraction. Orac discovers registry entities, current states, areas, devices,
service descriptions, and target-specific actions. It derives a bounded
semantic capability inventory without dispatching on manufacturer or model.

- [User and operator guide](home-assistant.md)
- [Architecture and capability model](home-assistant-architecture.md)
- [Data lifecycle](home-assistant-data-lifecycle.md)

The supplied APEX application is **Home Assistant Status**, application 10010
in the `ORAC` workspace. It parses as `ORAC_APX_PUB`, requires `ORAC_ADMIN`, and
is installed from `apex/f10010.sql` after the plugin database payload. The
application is a diagnostic surface; execution policy remains enforced by the
Orac host and cannot be weakened by the application.
