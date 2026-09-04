#!/usr/bin/env sh
set -eu

APP_ROOT=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
DEFAULT_REPOSITORY=https://github.com/viet15t12/NetworkTools.git
DEFAULT_BRANCH=main

usage() {
    cat <<'EOF'
Usage: ./update.sh [--check | --update]

Checks the configured CAMS Git repository and optionally installs the latest
commit. User data is preserved by install.sh.

Environment variables:
  CAMS_UPDATE_REPOSITORY  Git repository to check
  CAMS_UPDATE_BRANCH      Branch to check (default: main)
EOF
}

metadata_value() {
    line_number=$1
    if [ -f "$APP_ROOT/.cams-release" ]; then
        sed -n "${line_number}p" "$APP_ROOT/.cams-release"
    fi
}

current_commit=${CAMS_CURRENT_COMMIT:-}
repository=${CAMS_UPDATE_REPOSITORY:-}
branch=${CAMS_UPDATE_BRANCH:-}

if command -v git >/dev/null 2>&1 && git -C "$APP_ROOT" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    if [ -z "$current_commit" ]; then
        current_commit=$(git -C "$APP_ROOT" rev-parse HEAD 2>/dev/null || true)
    fi
    if [ -z "$repository" ]; then
        repository=$(git -C "$APP_ROOT" config --get remote.origin.url 2>/dev/null || true)
    fi
    if [ -z "$branch" ]; then
        branch=$(git -C "$APP_ROOT" branch --show-current 2>/dev/null || true)
    fi
fi

[ -n "$current_commit" ] || current_commit=$(metadata_value 1)
[ -n "$branch" ] || branch=$(metadata_value 2)
[ -n "$repository" ] || repository=$(metadata_value 3)
[ -n "$branch" ] || branch=$DEFAULT_BRANCH
[ -n "$repository" ] || repository=$DEFAULT_REPOSITORY
[ -n "$current_commit" ] || current_commit=unknown

case "$repository" in
    git@github.com:*) repository="https://github.com/${repository#git@github.com:}" ;;
    ssh://git@github.com/*) repository="https://github.com/${repository#ssh://git@github.com/}" ;;
esac

mode=${1:---update}
case "$mode" in
    --help|-h) usage; exit 0 ;;
    --check|--update) ;;
    *)
        echo "Unknown argument: $mode" >&2
        usage >&2
        exit 2
        ;;
esac

if ! command -v git >/dev/null 2>&1; then
    echo "ERROR: git is required to check for CAMS updates." >&2
    exit 1
fi

echo "Checking CAMS updates from $branch..."
remote_line=$(git ls-remote --exit-code "$repository" "refs/heads/$branch" 2>/dev/null) || {
    echo "ERROR: Could not reach the CAMS update repository." >&2
    exit 1
}
remote_commit=${remote_line%%[[:space:]]*}
if [ -z "$remote_commit" ]; then
    echo "ERROR: Branch '$branch' was not found in the CAMS update repository." >&2
    exit 1
fi

echo "CAMS_UPDATE_CURRENT=$current_commit"
echo "CAMS_UPDATE_LATEST=$remote_commit"

if [ "$current_commit" = "$remote_commit" ]; then
    echo "CAMS_UPDATE_STATUS=current"
    echo "CAMS is already up to date."
    exit 0
fi

if [ "$mode" = "--check" ]; then
    echo "CAMS_UPDATE_STATUS=available"
    echo "A CAMS update is available."
    exit 0
fi

checkout_dir=$(mktemp -d "${TMPDIR:-/tmp}/cams-update.XXXXXX")
cleanup() {
    rm -rf -- "$checkout_dir"
}
trap cleanup EXIT HUP INT TERM

echo "Downloading the latest CAMS version..."
if ! git clone --quiet --depth 1 --branch "$branch" "$repository" "$checkout_dir/source"; then
    echo "ERROR: Could not download the CAMS update." >&2
    exit 1
fi

downloaded_commit=$(git -C "$checkout_dir/source" rev-parse HEAD)
if [ "$downloaded_commit" != "$remote_commit" ]; then
    echo "ERROR: The downloaded CAMS commit does not match the checked commit." >&2
    exit 1
fi

echo "Installing the CAMS update..."
CAMS_UPDATE_REPOSITORY=$repository \
CAMS_UPDATE_BRANCH=$branch \
CAMS_UPDATE_COMMIT=$downloaded_commit \
    "$checkout_dir/source/install.sh"

echo "CAMS_UPDATE_STATUS=updated"
echo "CAMS was updated successfully. Restart the app to use the new version."
