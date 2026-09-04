# EIGRP QML File Roles

Reviewed: **2026-08-16**. This document summarizes each component in
`UI/qml/features/routing/eigrp`; backend behavior is documented in the feature
README and schema docs.

## `EigrpRoutingForm.qml`

Main coordinator component for the EIGRP screen.

- Manages global state: current host, loading/saving, dirty state, and active section.
- Loads and saves EIGRP data through `dbManager`.
- Owns `processModel` and the helper functions that mutate the selected process.
- Coordinates child sections by passing `form: eigrpRoutingForm`.
- Renders the `EigrpProcessCard` list in the `Process` tab.

## `EigrpProcessCard.qml`

Configuration card for one EIGRP process.

- Edits AS number, router ID, and process-level options.
- Configures auto summary, passive default, BFD all interfaces, metric weights, distance, variance, maximum paths, and stub options.
- Owns the per-process child models: networks, interface settings, passive interfaces, distribute lists, offset lists, redistribute, and key chains.
- Produces the save payload snapshot consumed by `EigrpRoutingForm.qml`.
- Validates process-level fields and network rows when networks exist.
- Note: an EIGRP process is not required to have a network.

## `EigrpPinnedHeader.qml`

Pinned header for the EIGRP screen.

- Shows always-visible summary cards: process count, network count, host, and state.
- Shows EIGRP navigation tabs: Process, Networks, Interfaces, Passive iface, Redistribute, Distribute list, Offset list, and Key chains.
- Calls `form.selectRoutingSection(...)` when the user switches tabs.

## `EigrpNetworksSection.qml`

EIGRP Networks configuration section.

- Adds network entries to the selected process.
- Supports optional wildcard and interface name.
- Displays the selected process network table.
- Removes network rows from the selected process.

## `EigrpInterfacesSection.qml`

EIGRP interface settings section.

- Adds interface settings to the selected process.
- Supports bandwidth, delay, hello/hold timers, auth key chain, summary address, split horizon, bandwidth percent, next-hop-self, and BFD timers.
- Displays/removes interface settings for the selected process.

## `EigrpPassiveInterfacesSection.qml`

EIGRP passive-interface configuration section.

- Adds interfaces to the selected process as `passive` or `no-passive` entries.
- Displays/removes passive-interface rows.

## `EigrpRedistributeSection.qml`

EIGRP redistribution configuration section.

- Adds redistribution rules by protocol.
- Supports route map and the five-part EIGRP metric: bandwidth, delay, reliability, load, and MTU.
- Displays/removes redistribution rules for the selected process.

## `EigrpDistributeListsSection.qml`

EIGRP distribute lists configuration section.

- Adds distribute-list entries by list name and `in`/`out` direction.
- Supports optional interface name.
- Displays/removes distribute-list rows for the selected process.

## `EigrpOffsetListsSection.qml`

EIGRP offset lists configuration section.

- Adds offset-list entries by list name, direction, and offset value.
- Supports optional interface name.
- Displays/removes offset-list rows for the selected process.

## `EigrpKeyChainsSection.qml`

EIGRP key chains configuration section.

- Adds key chains by chain name, key ID, and key string.
- Supports optional accept lifetime and send lifetime.
- Displays/removes key-chain rows for the selected process.
- Note: key chains are stored by host in the database, but the UI attaches them to the selected process for consistency with the EIGRP sections.
