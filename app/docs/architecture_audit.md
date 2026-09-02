# Application responsibility and Cython audit

Reviewed: **2026-08-16**.

This audit records why modules are split or retained and prevents line count
alone from driving risky refactors.

## High-priority boundaries

| Module | Current responsibilities | Decision |
|---|---|---|
| `features/devices/sync/_engine.py` | Parsing, conflict detection, interface and routing persistence | Public API split into `sync/parser.py`, `sync/interfaces.py`, `sync/routing.py`, and `sync/service.py`; compatibility kept in `sync_state.py`. Compiled optionally because parsing is CPU-bound. |
| `core/external_tools.py` | OS discovery, executable launch, catalog persistence, database browsing | Split next into discovery, launcher, repository, and QML facade. Do not compile: subprocess, registry, filesystem, SQLite, and Qt dominate. |
| `features/sftp/controller.py` | QML state, saved profiles, navigation, connection lifecycle, transfer queue | Keep the QML facade; move profile persistence and transfer orchestration behind services incrementally. Do not compile network I/O. |
| `core/settings.py` | System appearance plus window, theme, and status-bar settings | Classes are already cohesive but should move to an eventual `core/settings/` package with a compatibility facade. Do not compile Qt objects. |
| `infrastructure/system/virtual_lab.py` | Local VM evidence, guest address discovery, HTTP probing, result aggregation | Split probes by provider/API only alongside provider-level tests. Do not compile subprocess/network work. |
| `features/nat/nat_db.py` | Static NAT, interface roles, pools, PAT, ACL and route-map persistence | Split repositories by NAT aggregate. Do not compile SQLite wrappers. |
| `core/terminal.py` | QML facade, session commands, backup/sync workflow and async relays | Preserve facade contract; move workflow orchestration into feature services. Do not compile PyQt slots. |

## Cython policy

Cython is enabled only for measured CPU-bound modules that:

1. have stable Python inputs and outputs;
2. do not own `QObject`/signals;
3. do not spend most time in network, subprocess, filesystem, or SQLite calls;
4. pass the same contract tests in Python and native modes.

Currently `features.devices.sync._engine` is the only approved native module.
The native build is optional and the Python source remains the fallback.

## Operational entry points

- Linux/macOS: `./cams.sh`
- Windows: `cams.bat`

Both launchers check `uv`, synchronize the `speed` extra, attempt to build and
verify the native extension, and run the application through `uv run`. The
`setup` and `all` flows keep the documented Python fallback when a compiler or
OS policy prevents the optional extension from loading; the explicit `build`
flow remains strict.
