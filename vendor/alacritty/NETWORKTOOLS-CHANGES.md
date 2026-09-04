# CAMS changes to Alacritty

This directory is a modified source snapshot of
[Alacritty](https://github.com/alacritty/alacritty).

- Upstream baseline:
  `1b2b36a64e88068ad02c95fad00ee2fad31c00bf`
- Upstream baseline date: 2026-08-03
- Imported into CAMS by commit:
  `aeff1063ac77f0a1a731d98224de1d45b23f392e`
- Upstream package version at the baseline: `0.18.0-dev`
- CAMS binary name: `cams-terminal`

CAMS changed these upstream files:

- `alacritty/Cargo.toml`
- `alacritty/src/cli.rs`
- `alacritty/src/event.rs`
- `alacritty/src/main.rs`
- `alacritty/src/window_context.rs`

CAMS added this file:

- `alacritty/src/cams.rs`

The changes add the managed `--nt-*` command-line contract, NTTP/1 local-socket
client, managed window focus/close/title commands, session events, companion
branding, and hold behavior for the CAMS terminal process.

The original Alacritty copyright and license terms remain in
`LICENSE-APACHE` and `LICENSE-MIT`. The Alacritty application and terminal crate
declare Apache-2.0; the config crates declare MIT OR Apache-2.0. CAMS
does not claim ownership over unchanged upstream code.

This file records source provenance and modification notices. It is not a
replacement for the upstream licenses and is not legal advice.
