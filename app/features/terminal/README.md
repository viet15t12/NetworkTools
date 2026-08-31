# Managed external terminal

Trạng thái: **partial**. CAMS-side manager and NTTP/1 server are
implemented and fake-tested. The Alacritty source fork lives in
`vendor/alacritty`, accepts the managed CLI contract, and implements the Unix
NTTP/1 client/command dispatcher. Fedora/Wayland and EVE-NG acceptance remain.
Reviewed: **2026-08-18**.

Active composition never renders a terminal. It launches the separately
installed `networktools-terminal` process and lets that process own its window,
PTY, terminal parsing, input, clipboard, and SSH child.

## Ownership

- `session.py`: UUID-based session DTO with separate process, window, IPC, and
  SSH-child states. It never stores a password.
- `ssh.py`: fail-closed host/username/port validation and SSH child selection.
- `interactive_ssh.py`: isolated Paramiko PTY relay for legacy Cisco IOS hosts
  rejected by Fedora libcrypto; it reads credentials from the active workspace
  and never receives a password through argv, environment, IPC, or logs.
- `launcher.py`: companion binary discovery and the `--nt-*` managed launch
  contract passed directly to `QProcess` without a shell.
- `protocol.py`: versioned NTTP/1 JSON Lines validation, allowlisted events and
  commands, and a 64 KiB message limit.
- `ipc_server.py`: `QLocalServer` endpoint in a user-owned `0700` runtime
  directory with a `0600` socket, registered-session checks, request IDs, and
  bounded timeouts.
- `managed_manager.py`: one managed session per inventory host, duplicate-open
  focus, lifecycle aggregation, graceful close fallback, crash cleanup, and
  restart.

The stable QML context is still `cli`. Its public terminal contract is:

```text
openDeviceTerminal(host)
focusDeviceTerminal(host)
closeDeviceTerminal(host)
restartDeviceTerminal(host)
isDeviceTerminalOpen(host)
deviceTerminalState(host)
terminalStateChanged(host, state)
terminalError(host, message)
```

UI states are `closed`, `starting`, `open`, `disconnected`, and `error`. QML does
not receive detailed process/IPC state and does not contain process or protocol
logic.

## Persistence and network behavior

This feature has no tables. It reads normalized device metadata through
`DeviceLoginService`. Stored passwords are intentionally excluded from session
objects, process arguments, IPC, messages, and logs. Interactive SSH is a new
connection and is not shared with the automation
`DeviceSessionRegistry`.

Modern devices use system OpenSSH and reuse saved `t01_ssh_algo` preferences.
An inventory row identified as `cisco_ios` uses the isolated Paramiko PTY child
because Fedora libcrypto rejects SHA-1 signatures from older IOS images. This
does not change Fedora's system-wide crypto policy. Saved algorithm values are
also applied to this adapter.

Managed windows force Alacritty's hold behavior. If the SSH child exits during
verification, negotiation, or authentication, the window remains visible so
the user can read the error and close it explicitly.

devices in development mode, unknown inventory rows, Telnet, unsafe host/user/port values,
a missing companion binary, and an unavailable safe runtime directory all fail
closed before a process starts. Automated tests never start SSH or contact a
device.

## NTTP/1

Terminal events are `terminal.started`, `terminal.ready`, `child.started`,
`child.exited`, `terminal.closed`, and `terminal.error`. Manager commands are
`window.focus`, `window.close`, `window.set_title`, `session.ping`, and
`session.get_info`. NTTP/1 does not carry terminal output, passwords, screen
content, database data, or arbitrary commands.

## Tests and known limits

`tests/unit/test_managed_terminal.py` covers launch/security, lifecycle,
duplicate prevention, crash cleanup, protocol validation, fragmented local
socket input, permissions, and unknown-session rejection. The socket cases need
an environment that permits creation of Unix sockets.

The former embedded implementation remains in `manager.py`, `window.py`,
`worker.py`, and `stream.py` only as inactive migration compatibility code with
its existing tests. It is not instantiated by `TerminalHelper`. Removing that
code, `qtpyTerminal-main`, and its Python dependencies is deferred to a focused
cleanup after companion-fork end-to-end acceptance.

The companion still needs final branding, packaging and real
Fedora/Wayland/Cisco evidence. Its upstream Apache-2.0/MIT notices are retained
inside `vendor/alacritty`. `networktools.sh setup` builds the release binary and
the Python launcher discovers it without modifying `PATH`.

The vendored baseline is Alacritty commit
`1b2b36a64e88068ad02c95fad00ee2fad31c00bf` (`0.18.0-dev`). CAMS
modification notices and the exact changed-file list are maintained in
`vendor/alacritty/NETWORKTOOLS-CHANGES.md`; repository placement and release
license obligations are documented in `vendor/README.md`. `target/` is a local
ignored build directory and must never be committed or packaged as source.
