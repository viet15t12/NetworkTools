# ADR-0001: Use an External Alacritty-Based Terminal and NTTP/1

## Status

Accepted on 2026-08-12; amended on **2026-08-16** after the companion source was
vendored for reproducible builds.

## Context

CAMS needs a high-performance interactive device CLI with native
terminal behavior. Embedding a terminal parser and renderer in the PyQt6/QML
application couples human terminal I/O to the same Netmiko sessions used by
automation, makes terminal correctness an application responsibility, and does
not provide the independent-window lifecycle described by the product roadmap.

The terminal must not gain access to CAMS persistence, configuration
generators, credentials, or automation internals. The Alacritty fork also needs
to remain close enough to upstream for routine rebases.

## Decision

Use a separate-process **CAMS Terminal** based on Alacritty. Its source
is vendored under `app/vendor/alacritty` so the app launcher can build a matching
binary from one checkout. Process/runtime ownership remains separate even though
the source currently shares this repository. CAMS launches it with
`QProcess`, assigns a UUID session ID, and tracks one active managed session per
inventory host.

The applications exchange versioned NTTP/1 JSON Lines over a user-only Unix
domain socket below `$XDG_RUNTIME_DIR/cams/`. `QProcess` owns spawn,
PID, exit, and crash evidence. NTTP/1 owns lifecycle events and the allowlisted
focus, close, title, ping, and session-info commands. Messages are limited to 64
KiB and never carry terminal output, arbitrary commands, or credentials.

Interactive access uses system OpenSSH as the terminal child. CAMS
passes an argument list directly and never uses a shell or places the inventory
password on argv. Existing Netmiko sessions remain dedicated to automation.

The maintained Python implementation lives in `app/features/terminal/`; the
stable QML context remains the thin `core.terminal.TerminalHelper` facade. The
old embedded qtpyTerminal/Netmiko implementation is not part of active
composition and is retained temporarily only as migration evidence until its
vendored dependency can be removed in a separately reviewed cleanup.

## Consequences

- Terminal rendering, PTY, ANSI/VT, input, clipboard, and scrollback stay in a
  mature terminal application.
- CAMS can distinguish process state from window, IPC, and SSH-child
  state and does not use PID or title as identity.
- A missing companion binary fails with an actionable error instead of silently
  launching a generic system terminal.
- The Linux manager can be tested with fake processes and clients without
  contacting devices. Rendering and Wayland focus still require manual tests.
- Windows needs a different local transport, while the JSON protocol can remain
  unchanged.
- Full delivery still depends on final branding/packaging and Fedora/EVE-NG
  acceptance evidence. Upstream provenance and license notices must remain.

## Rejected alternatives

- Continue rendering the terminal in QML/QWidget: violates the fixed process and
  ownership boundary.
- Keep only an opaque prebuilt binary: rejected because it prevents reproducible
  source builds and makes the Python/NTTP contract harder to keep in lockstep.
- Use PID, title, `pgrep`, `wmctrl`, or `xdotool` as session control: identities
  are ambiguous and X11-specific focus does not work as a Wayland architecture.
- Use localhost TCP or arbitrary-command IPC: unnecessarily expands exposure.
- Share a live automation SSH socket with the human terminal: couples two
  concurrency and lifecycle models.
