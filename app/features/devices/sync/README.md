# Device state sync

Status: **implemented** with an optional Cython accelerator and Python fallback.
Reviewed: **2026-08-18**.

The package separates the public synchronization surface by responsibility:

- `parser.py`: running-config parsing
- `interfaces.py`: interface SQLite writers
- `fhrp.py`: HSRP, VRRP, and GLBP SQLite writers
- `dhcp.py`: interface DHCP relay/helper SQLite writer
- `routing.py`: static route, OSPF, and EIGRP writers
- `service.py`: transaction-level orchestration
- `common.py`: shared normalization helpers
- `_engine.py`: single-source implementation compiled by the optional Cython build

`features.devices.sync_state` remains a compatibility module. Existing imports
continue to work without changes.

Router interface inventory is rebuilt from the union of parsed running-config
interface blocks and `show ip interface brief`. Synchronized rows missing from
the next collected snapshot are deleted from SQLite rather than marked as a
desired-state removal, so Router Interface UI is fully database-derived and a
collection cannot accidentally queue `no interface` commands.
The interface brief is reconciled even when the committed running-config text is
unchanged, because physical inventory can change independently of configuration.

FHRP configuration is parsed from each interface block and synchronized per
device member. Shared logical groups are retained for other devices. Safe mode
preserves pending FHRP changes; force-device-state mode replaces them with the
observed HSRP, VRRP, and GLBP configuration.

IPv4 `ip helper-address` commands are collected from router interface blocks
and synchronized into `t03_router_iface_helper`. Multiple helpers per interface
are preserved. Safe mode leaves pending helper changes untouched.

Subinterfaces are classified independently from physical L3 profiles. The
parser records `dot1Q`/`isl`, VLAN ID and the optional native flag, while the
SQLite writer preserves the implied physical parent even when only the
subinterface appears in the collected snapshot. Child profiles absent from an
observed snapshot are deleted locally; they are never left as
`pending_delete` work for a later View & Push. This prevents legacy
Subinterface-as-L3 rows from generating unsupported physical-interface cleanup
commands.

The normal installation uses `_engine.py`. To build the same implementation as
a native extension:

```shell
uv sync --extra speed
uv run python setup_cython.py build_ext --inplace
```

The resulting `_engine.*.so` (Linux/macOS) or `_engine*.pyd` (Windows) is loaded
automatically before `_engine.py`. Delete only that generated extension to
return to the Python implementation.

`networktools.sh setup` and `networktools.bat setup` attempt this optional build
but fall back to `_engine.py` when a compiler is unavailable or an OS policy
blocks the native module. Use the explicit `build` command when native
acceleration is required and a failed build should return a non-zero status.
On Linux, the optional setup checks for the active interpreter's `Python.h`
first, so a missing development-header package selects the Python fallback
without emitting a full compiler failure. The explicit `build` command remains
strict and reports the missing prerequisite.
On Windows, the batch launcher can replace a blocked accelerated Cython wheel
with Cython's pure-Python compiler, but building the app's `.pyd` still requires
Microsoft Visual C++ 14.0 or newer.

Always benchmark the full synchronization path. Cython primarily helps parsing
and Python control flow; SQLite execution time is already spent in native code.
