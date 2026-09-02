# SFTP behavior contract

Reviewed: **2026-08-16**. Operational/security details live in
[`../SFTP.md`](../SFTP.md).

## UI-06: external client activation

The SFTP ActivityBar action is the decision point:

1. When an enabled `SFTP Client` exists in External Tools, clicking SFTP
   launches that executable and keeps CAMS on its current workspace.
2. If a saved SFTP profile is already selected, the launcher substitutes
   `{ip}`, `{port}`, `{username}`, and `{path}`.
3. Without a selected profile, target-dependent arguments are omitted so
   WinSCP/FileZilla opens its own login or saved-session UI.
4. If no external client is active, CAMS opens the built-in SFTP
   workspace.
5. If the executable is missing, process creation fails, or a legacy
   `{password}` argument is found, CAMS reports a warning and opens the
   built-in workspace.

Passwords are never accepted as an External Tools placeholder and are never
placed on a process command line.

## UI-06: navigation

- `Alt+Left` and `Alt+Right` follow the active local/remote pane history.
- Mouse Back/Forward follows the same history.
- Keyboard shortcuts remain disabled while a text input has focus.
- Shortcuts owned by hidden panels are disabled. `Ctrl+Shift+N` belongs only
  to SFTP New Folder; Batch New Device uses the distinct `Ctrl+Alt+N` sequence.
- `Ctrl+R` is owned by the application command registry and dispatches refresh
  to the active SFTP pane; `F5` remains a local SFTP shortcut.
- Physical mouse Back/Forward remains enabled while a connection/path input
  has focus; only an active modal lock disables it.
- Each pane exposes disabled Back/Forward buttons when its history has no
  matching destination.

The mouse behavior has an offscreen pointer test that focuses the local path
field before sending `Qt.BackButton` and `Qt.ForwardButton`. This reproduces the
previous failure condition and verifies both path transitions.

## UI-07: file metadata

- `Type` is independent from `Size`; a directory is reported as `Folder`.
- Directory sizes and unavailable file sizes display `-`.
- A known empty file displays `0 B`, so missing metadata is not confused with
  a valid zero-byte value.
- Common network/configuration extensions receive human-readable type labels;
  unknown extensions use a stable `<EXT> file` fallback.

## UI-07: selection and context menu

- A plain click selects one row, Ctrl+click toggles one row, Shift+click selects
  a range, and Ctrl+Shift+click adds a range.
- Ctrl+A selects all rows and Escape clears the active pane selection.
- Right-clicking a selected row preserves a multi-selection. Right-clicking an
  unselected row selects that row before opening the menu.
- Rename requires exactly one row. Upload, Download, and Delete operate on all
  selected rows.
- The context menu exposes only implemented actions: Open/Transfer, Rename,
  Delete, New folder, Select all, and Refresh. Shift+F10 opens it from the
  keyboard.
- File context menus are non-modal, matching the Device context menu: opening
  one does not set `UiState.windowLock`, blur the main workspace, or activate a
  modal scrim. The full-window outside-click catcher still closes the menu.

## UI-08: password persistence

- Password persistence is disabled by default.
- A connection profile stores only a `passwordSaved` capability flag. The
  plaintext password is never placed in the saved-connections JSON or exposed
  in the public profile map.
- Per-profile saving requires an explicit checkbox. Clearing the checkbox and
  saving the profile removes its protected credential.
- Global automatic saving is a separate, explicit SFTP setting. It applies only
  after a successful connection and does not silently enable itself.
- On Windows, credentials are protected by DPAPI for the current signed-in
  user. Machine-wide scope is not used. If secure storage is unavailable, both
  saving options are disabled.
- Saving remains labeled “not recommended”; private-key authentication and an
  SSH agent are preferred.
- External clients never receive the password, including when the integrated
  client has a saved credential.

## References

- [WinSCP Commander keyboard shortcuts](https://winscp.net/eng/docs/ui_commander_key)
- [WinSCP directory navigation](https://winscp.net/eng/docs/task_navigate)
- [WinSCP file panels](https://winscp.net/eng/docs/ui_file_panel)
- [WinSCP scripting/URL syntax](https://winscp.net/eng/docs/session_url)
- [Microsoft CryptProtectData](https://learn.microsoft.com/en-us/windows/win32/api/dpapi/nf-dpapi-cryptprotectdata)
- [WinSCP credential security](https://winscp.net/eng/docs/security_credentials)
