#!/usr/bin/env bash
# Run from any directory; repeated runs leave the renamed folders in place.
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.."

# Check both destinations before making any changes.
for name in report book; do
    if [[ -e "$name" || -L "$name" ]]; then
        if [[ ! -d "$name" || -L "$name" ]]; then
            printf 'Expected a directory: %s\n' "$name" >&2
            exit 1
        fi
        if [[ -e "00_$name" || -L "00_$name" ]]; then
            printf 'Cannot rename %s: 00_%s already exists.\n' "$name" "$name" >&2
            exit 1
        fi
    fi
done

for name in report book; do
    if [[ -d "$name" ]]; then
        mv -T --no-clobber -- "$name" "00_$name"
        if [[ -e "$name" ]]; then
            printf 'Rename failed: %s\n' "$name" >&2
            exit 1
        fi
        printf 'Renamed %s -> 00_%s\n' "$name" "$name"
    fi
done
