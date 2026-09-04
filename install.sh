#!/usr/bin/env sh
set -eu

SOURCE_ROOT=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)

if [ "${1:-}" = "--help" ] || [ "${1:-}" = "-h" ]; then
    cat <<'EOF'
Usage: ./install.sh

Installs CAMS for the current Linux user, creates the `cams` command and adds
CAMS to the desktop application menu. Existing user data is preserved.

Optional environment variables:
  CAMS_INSTALL_BASE  Program/data base directory (default: XDG data/cams)
  CAMS_BIN_DIR       Command directory (default: ~/.local/bin)
EOF
    exit 0
fi

if [ "$#" -ne 0 ]; then
    echo "Unknown argument: $1" >&2
    echo "Run ./install.sh --help for usage." >&2
    exit 2
fi

if [ -z "${HOME:-}" ]; then
    echo "ERROR: HOME is not set." >&2
    exit 1
fi
if ! command -v tar >/dev/null 2>&1; then
    echo "ERROR: tar is required to install CAMS." >&2
    exit 1
fi
if [ "${CAMS_INSTALL_SKIP_SETUP:-0}" != "1" ] && ! command -v uv >/dev/null 2>&1; then
    echo "ERROR: uv is required to install CAMS." >&2
    echo "Install uv from https://docs.astral.sh/uv/ and run this installer again." >&2
    exit 1
fi

data_home=${XDG_DATA_HOME:-$HOME/.local/share}
install_base=${CAMS_INSTALL_BASE:-$data_home/cams}
app_dir=$install_base/app
user_data_dir=$install_base/data
bin_dir=${CAMS_BIN_DIR:-$HOME/.local/bin}
applications_dir=$data_home/applications
icon_theme_dir=$data_home/icons/hicolor
scalable_icons_dir=$icon_theme_dir/scalable/apps
bitmap_icons_dir=$icon_theme_dir/256x256/apps

case "$app_dir" in
    ""|/|"$HOME"|"$data_home"|"$install_base")
        echo "ERROR: Refusing unsafe install directory: $app_dir" >&2
        exit 1
        ;;
esac

archive=$(mktemp "${TMPDIR:-/tmp}/cams-install.XXXXXX.tar")
cleanup() {
    rm -f -- "$archive"
}
trap cleanup EXIT HUP INT TERM

echo "Preparing CAMS program files..."
tar -C "$SOURCE_ROOT" \
    --exclude='__pycache__' \
    --exclude='*.pyc' \
    --exclude='*.pyo' \
    --exclude='*.db' \
    --exclude='*.db-*' \
    --exclude='build' \
    --exclude='target' \
    --exclude='*.egg-info' \
    -cf "$archive" \
    UI bin core data/README.md docshots domain features infrastructure native \
    qtpyTerminal-main runtime_qml scripts templates vendor licenses \
    .python-version README.md LICENSE app_facade.py cams.sh main.py \
    pyproject.toml setup_cython.py uv.lock packaging/linux/cams-launcher

# Program files are replaceable; user databases live in the sibling data/
# directory and are deliberately never removed during an install or upgrade.
rm -rf -- "$app_dir"
mkdir -p "$app_dir" "$user_data_dir" "$bin_dir" "$applications_dir" \
    "$scalable_icons_dir" "$bitmap_icons_dir"
tar -C "$app_dir" -xf "$archive"
install -m 0755 "$app_dir/packaging/linux/cams-launcher" "$app_dir/cams-launcher"

if [ "${CAMS_INSTALL_SKIP_SETUP:-0}" != "1" ]; then
    echo "Installing Python dependencies..."
    (cd "$app_dir" && ./cams.sh sync)

    if ! (cd "$app_dir" && ./cams.sh build); then
        echo "WARNING: Cython acceleration is unavailable; CAMS will use Python fallback." >&2
    fi
    if ! (cd "$app_dir" && ./cams.sh syslog-build); then
        echo "WARNING: Native Syslog support was not built. Install CMake and a C++ compiler, then rerun the installer." >&2
    fi
    if ! (cd "$app_dir" && ./cams.sh terminal-build); then
        echo "WARNING: CAMS Terminal was not built. Install Rust and native font/X11 development libraries, then rerun the installer." >&2
    fi
fi

ln -sfn "$app_dir/cams-launcher" "$bin_dir/cams"
install -m 0644 "$SOURCE_ROOT/UI/resources/brand/logo.svg" "$scalable_icons_dir/cams.svg"
install -m 0644 "$SOURCE_ROOT/UI/resources/brand/logo.png" "$bitmap_icons_dir/cams.png"

cat > "$applications_dir/cams.desktop" <<EOF
[Desktop Entry]
Type=Application
Version=1.0
Name=CAMS
Comment=Centralized network device management and automation
Exec="$bin_dir/cams"
Icon=$scalable_icons_dir/cams.svg
Terminal=false
Categories=Network;Utility;
StartupNotify=true
StartupWMClass=CAMS
EOF
chmod 0644 "$applications_dir/cams.desktop"

if command -v update-desktop-database >/dev/null 2>&1; then
    update-desktop-database "$applications_dir" >/dev/null 2>&1 || true
fi
if command -v gtk-update-icon-cache >/dev/null 2>&1; then
    gtk-update-icon-cache -f -t "$icon_theme_dir" >/dev/null 2>&1 || true
fi

echo
echo "CAMS was installed successfully."
echo "  Application menu: CAMS"
echo "  Command:          $bin_dir/cams"
echo "  Program files:    $app_dir"
echo "  User data:        $user_data_dir"
case ":${PATH:-}:" in
    *:"$bin_dir":*) ;;
    *) echo "  PATH note: add $bin_dir to PATH to run 'cams' from a terminal." ;;
esac
