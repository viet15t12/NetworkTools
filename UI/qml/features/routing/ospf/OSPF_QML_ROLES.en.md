# OSPF QML File Roles

Reviewed: **2026-08-16**. This document summarizes each component in
`UI/qml/features/routing/ospf`; backend behavior is documented in the feature
README and schema docs.

## `OspfRoutingForm.qml`

Main coordinator component for the OSPF screen.

- Manages global state: current host, loading/saving, dirty state, and active section.
- Loads and saves OSPF data through `dbManager`.
- Owns `processModel` and the helper functions that mutate the selected process.
- Coordinates child sections by passing `form: ospfRoutingForm`.
- Renders the `OspfProcessCard` list in the `Process` tab.

## `OspfProcessCard.qml`

Configuration card for one OSPF process.

- Edits process ID, router ID, and reference bandwidth.
- Edits process-level options: passive default, default originate, and always.
- Owns the per-process child models: networks, areas, redistribute, passive interfaces, and interface settings.
- Produces the save payload snapshot consumed by `OspfRoutingForm.qml`.
- Validates process-level fields and network rows when networks exist.

## `OspfPinnedHeader.qml`

Pinned header for the OSPF screen.

- Shows always-visible summary cards: process count, network count, host, and state.
- Shows OSPF navigation tabs: Process, Networks, Areas, Distance, Redistribute, Interfaces, Passive iface, and Tuning.
- Calls `form.selectRoutingSection(...)` when the user switches tabs.

## `OspfAreasSection.qml`

OSPF Areas configuration section.

- Adds/removes areas for the selected process.
- Configures area type, no-summary, and authentication.
- Adds/removes area ranges for the selected area.
- Uses area/range helper functions from `OspfRoutingForm.qml`.

## `OspfNetworksSection.qml`

OSPF Networks configuration section.

- Adds network/wildcard/area entries to the selected process.
- Displays the selected process network table.
- Removes network rows from the selected process.
- Note: an OSPF process is not required to have a network.

## `OspfDistanceSection.qml`

OSPF administrative distance section.

- Edits external, intra-area, and inter-area distance.
- Calls `form.setDistanceForSelectedProcess(...)` to update the selected process.

## `OspfRedistributeSection.qml`

OSPF redistribution configuration section.

- Adds redistribution rules by protocol.
- Supports optional process ID, subnets, metric, metric type, and route map.
- Displays/removes redistribution rules for the selected process.

## `OspfInterfacesSection.qml`

OSPF interface settings section.

- Adds interface settings to the selected process.
- Supports area, cost, hello/dead interval, MTU ignore, BFD, network type, and auth type.
- Displays/removes interface settings for the selected process.

## `OspfPassiveInterfacesSection.qml`

Passive-interface configuration section.

- Adds interfaces to the selected process as passive/no-passive entries.
- Displays/removes passive-interface rows.

## `OspfTuningSection.qml`

OSPF tuning section.

- Updates maximum paths and max LSA.
- Updates SPF timers and LSA timers.
- Calls `form.setTuningForSelectedProcess(...)` to update the selected process.
