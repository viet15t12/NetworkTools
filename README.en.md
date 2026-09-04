<!-- markdownlint-disable MD033 MD041 -->
[English](README.en.md) | [Tiếng Việt](README.md)
<div align="center">
  <img src="UI/resources/brand/logo_readme.svg" alt="CAMS logo" width="144">

  <img src="UI/resources/brand/name.svg" alt="CAMS name">

  <p><strong>A desktop platform for centralized network device management, configuration, and monitoring.</strong></p>

  <p>
    <img alt="Python" src="https://img.shields.io/badge/Python-%E2%89%A53.11-3776AB?logo=python&logoColor=white">
    <img alt="PyQt6" src="https://img.shields.io/badge/UI-PyQt6%20%2B%20QML-41CD52?logo=qt&logoColor=white">
    <img alt="SQLite" src="https://img.shields.io/badge/Database-SQLite-003B57?logo=sqlite&logoColor=white">
    <img alt="Status" src="https://img.shields.io/badge/Status-Development-F59E0B">
  </p>
</div>

<img src="UI/resources/brand/stats-dark.svg" alt="stats-dark">

## Overview

CAMS provides a unified interface for managing device inventory, tracking status, and building configurations for routers, switches, and network services. The application combines a Qt Quick/QML interface with a Python backend, stores data locally in SQLite, and communicates with devices over SSH/Telnet.

The project is developed as part of a research initiative:

> Researching and building a centralized management system for automated network configuration and security monitoring.

## Key Features

| Feature area | Capabilities |
| --- | --- |
| Device management | Add, edit, delete, bulk import, ping, and concurrently connect/sync multiple hosts |
| Network configuration | DHCP, ACL, NAT, FHRP, Router Interface View & Push, static routes, OSPF, and EIGRP |
| Switching | Switchports, VLANs, SVI/L3, View & Push, and Cisco IOS VLAN/interface/EtherChannel/VTP pull-sync |
| Terminal & sessions | Open a CLI, manage session lifecycle, run commands, and save running-config to startup-config |
| Configuration backup | Store running-config history per device using Dulwich |
| System Logs | Receive, filter, and store Syslog messages over UDP/TCP |
| Device Logs | Capture and analyze traffic with TShark in a permission-scoped environment |
| SFTP | Browse files, upload/download, and track the file transfer queue |
| External tools | Integration with SSH clients, terminal emulators, and an SQLite browser on the user's machine |
| Project/workspace | `.ntp` packages, optional encryption, snapshots, and rollback |

> Some configuration workflows depend on the vendor, protocol, and lab device involved. Always preview commands and test in dev-mode before pushing configuration to a real device.

## System Requirements

- Python **3.11 or later**;
- [`uv`](https://docs.astral.sh/uv/) for environment and dependency management;
- Windows is the primary development platform; Linux requires the corresponding Qt libraries to be fully installed;
- TShark/Wireshark if using the Device Logs feature;
- valid access credentials to network devices when using real connections.

## Quick Start

### Linux: install as a desktop application

```bash
git clone https://github.com/ntdatphu/CAMS.git
cd CAMS
./install.sh
```

After the first installation, open **CAMS** from the application menu or run
`cams` in a terminal. You no longer need to enter the repository or run
`cams.sh run`. The user-local installer requires no `sudo`, keeps program files
under `~/.local/share/cams/app`, creates a launcher in `~/.local/bin`, and stores
user databases separately under `~/.local/share/cams/data`. Run `./install.sh`
again to upgrade without deleting user data.

Use `./uninstall.sh` to remove the program. Pass `--purge-data` only when local
databases and settings should also be removed.

### Run directly for development

```bash
./cams.sh setup
./cams.sh run
```

Development commands run from the repository root. `uv` creates the environment
from `pyproject.toml` and `uv.lock`; set `CAMS_DATA_DIR` to use another data path.

## Usage Guide

### Adding and connecting a device

1. Open the **Devices** area and select **Add Device**, or press `Ctrl+N`.
2. Enter the host address, protocol, port, login credentials, operating system, and device role.
3. Save the device; its initial status will be `Waiting`/`Pending`.
4. Open the device's context menu to **Ping**, **Connect**, **Reconnect**, view the **Running Config**, **Save configuration** to startup-config, or open the **CLI**.
   Use **Connect All Waiting** from the group menu to start independent host
   connection tasks concurrently.
5. Only store credentials used in your lab environment, and never commit the runtime database to Git.

### Testing with dev-mode

1. Add a mock device using lab information.
2. Once the device is in the `Waiting` state, select **Up (Dev)**.
3. Create or edit a local configuration.
4. Use **View & Push** to preview the result before applying it to a real device.

Dev-mode simulates pushes for Routing, DHCP, ACL, and NAT. Interfaces, FHRP,
Switching, Syslog device configuration, SFTP, and the terminal do not implicitly
inherit that behavior; dev-mode is not the only required safeguard.

### Building and deploying a configuration

1. Select an active device.
2. Open the feature you want to configure: Routing, DHCP, ACL, NAT, Interface, or Switching.
3. Enter the data and save the configuration locally.
4. Review the preview, target host, vendor, and protocol.
5. Back up the running-config before selecting **Push**.
6. Monitor the task status and re-verify the configuration on the device once it completes.

Router Interface View & Push supports Cisco IOS over SSH/Telnet for IPv4
addressing, secondary addresses, L3 tuning, WAN, and Tunnel profiles. Physical
interfaces can only be edited after they have been synchronized; only virtual
interfaces can be created or deleted. PPP
passwords are redacted from previews and reports, and database rows are marked
applied only after the device accepts the command batch. RESTCONF/NETCONF, IPv6,
post-push verification, and automatic rollback are not integrated yet; see
[`features/interfaces/README.md`](features/interfaces/README.md).

Switching uses the same View & Push flow for VLANs, switch ports/EtherChannel,
STP, VTP, and Layer 2 security over SSH/Telnet. Each module is marked synchronized
only after the device accepts its commands. See
[`features/switching/INTEGRATION_LIMITATIONS.md`](features/switching/INTEGRATION_LIMITATIONS.md).

Configuration Backup stores per-host Dulwich history in `.cams-git`.
When a workspace is saved, the staging process migrates the former `.git` layout
so `.ntp` packages can continue rejecting standard Git metadata without losing
the saved configuration history.

### Syslog, Device Logs, and SFTP

- **System Logs:** configure the listener under **Settings → System Logs**, verify the bind address/port, then start the listener from the Activity Bar.
- **Device Logs:** choose the capture interface and filters before capturing packets; only use this on networks you are authorized to monitor.
- **SFTP:** verify the server's SHA-256 fingerprint before accepting the
  connection and transferring files; see the [SFTP guide](docs/SFTP.md).

Detailed instructions for each screen are available in [docs/USAGE_GUIDE.md](docs/USAGE_GUIDE.md). The list of keyboard shortcuts is in [docs/SHORTCUTS.md](docs/SHORTCUTS.md).

## Architecture

```text
QML / Qt Quick
      │
      ▼
Core facade & context properties
      │
      ▼
Feature services / repositories / workers
      │
      ├── SQLite
      └── Network adapters ──► Devices
```

| Path | Role |
| --- | --- |
| `UI/`, `core/`, `features/` | Interface, facade, and application business logic |
| `infrastructure/` | Database, system, and network connection adapters |
| `scripts/`, `tests/` | Build/validation tools and the test suite |
| `archive/backend/` | Experimental/legacy code not loaded by the desktop composition root |
| `docs/` | Usage, architecture, and technical convention documentation |
| `docs/research/` | Research report and Typst book sources, separate from runtime |
| `packaging/` | Application launcher and packaging resources |

Read more in [System Architecture](docs/ARCHITECTURE.md) and [Project Structure](docs/PROJECT_STRUCTURE.md).

## Testing and Quality Checks

Run the following commands from the repository root:

```bash
uv run python scripts/validate_structure.py
uv run python -m compileall .
uv run python -m unittest discover -s tests -v
```

Runtime databases, logs, caches, credentials, private keys, and local backups must not be committed.

## Documentation

- [Documentation map](docs/README.md)
- [Usage Guide](docs/USAGE_GUIDE.md)
- [Technical Architecture](docs/ARCHITECTURE.md)
- [Directory Structure](docs/PROJECT_STRUCTURE.md)
- [Database Schema](docs/DATABASE_SCHEMA.md)
- [UI Components](docs/UI_COMPONENTS.md)
- [System Logs](docs/SYSTEM_LOGS.md)
- [SFTP](docs/SFTP.md)
- [Shortcuts](docs/SHORTCUTS.md)
- [Code Audit Report](docs/CODE_AUDIT.md)
- [Current App Features](docs/CURRENT_APP_FEATURES.md)
- [Backend/App comparison](docs/BACKEND_APP_PARITY.md)
- [Changelog](CHANGELOG.md)
- [Roadmap](ROADMAP.md)
- [Contributing Guide](CONTRIBUTING.md)
- [Coding Standards](docs/CODING_STANDARDS.md)
- [Authors and Research Contributors](AUTHORS.md)

## Operational Safety

- Only connect to, capture packets from, and change the configuration of systems you are authorized to access.
- Never place passwords in command-line arguments, logs, screenshots, or commits.
- Always back up configurations and databases before rebuilding or pushing.
- Verify the target device, preview content, and dev-mode status before every deployment action.
- Do not expose the API, Syslog listener, or database to a public network without proper authentication and access control in place.

## Project Status

CAMS is currently in development and undergoing verification in a research/lab environment. The API, some backend workers, and some View & Push flows are still being finalized; it should not be used as a production system without integration testing on the target infrastructure.
