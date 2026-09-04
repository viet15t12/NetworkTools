#!/usr/bin/env sh
set -eu

if [ -z "${HOME:-}" ]; then
    echo "ERROR: HOME is not set." >&2
    exit 1
fi

purge=0
case "${1:-}" in
    "") ;;
    --purge-data) purge=1 ;;
    --help|-h)
        echo "Usage: ./uninstall.sh [--purge-data]"
        echo "Without --purge-data, local databases and settings are preserved."
        exit 0
        ;;
    *)
        echo "Unknown argument: $1" >&2
        exit 2
        ;;
esac

data_home=${XDG_DATA_HOME:-$HOME/.local/share}
install_base=${CAMS_INSTALL_BASE:-$data_home/cams}
app_dir=$install_base/app
user_data_dir=$install_base/data
bin_dir=${CAMS_BIN_DIR:-$HOME/.local/bin}

case "$app_dir" in
    ""|/|"$HOME"|"$data_home"|"$install_base")
        echo "ERROR: Refusing unsafe install directory: $app_dir" >&2
        exit 1
        ;;
esac

rm -rf -- "$app_dir"
rm -f -- "$bin_dir/cams"
rm -f -- "$data_home/applications/cams.desktop"
rm -f -- "$data_home/icons/hicolor/scalable/apps/cams.svg"
rm -f -- "$data_home/icons/hicolor/256x256/apps/cams.png"

if [ "$purge" -eq 1 ]; then
    rm -rf -- "$user_data_dir"
    rmdir "$install_base" 2>/dev/null || true
    echo "CAMS and its user data were removed."
else
    echo "CAMS was removed. User data was preserved at $user_data_dir"
fi

if command -v update-desktop-database >/dev/null 2>&1; then
    update-desktop-database "$data_home/applications" >/dev/null 2>&1 || true
fi
if command -v gtk-update-icon-cache >/dev/null 2>&1; then
    gtk-update-icon-cache -f -t "$data_home/icons/hicolor" >/dev/null 2>&1 || true
fi
