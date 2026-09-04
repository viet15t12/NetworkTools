#!/usr/bin/env bash

# ============================================================
# build_sql.sh
#
# Ghép các file SQL nguồn thành hai file SQL tổng hợp:
#
#   schema/*.sql
#       -> device_network.sql
#
#   info_collected/*.sql
#       -> info_collected.sql
#
# Các file SQL được sắp xếp tự nhiên theo tên:
#   01_..., 02_..., 10_..., 11_...
#
# Tên file có khoảng trắng vẫn được hỗ trợ.
# ============================================================

set -Eeuo pipefail

ROOT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"

SCHEMA_DIR="$ROOT_DIR/schema"
INFO_DIR="$ROOT_DIR/info_collected"

DEVICE_SQL="$ROOT_DIR/device_network.sql"
INFO_SQL="$ROOT_DIR/info_collected.sql"


# ============================================================
# Hàm hỗ trợ
# ============================================================

print_error() {
    printf 'Lỗi: %s\n' "$1" >&2
}

check_dependencies() {
    if ! command -v find >/dev/null 2>&1; then
        print_error "Không tìm thấy lệnh find."
        exit 1
    fi

    if ! command -v sort >/dev/null 2>&1; then
        print_error "Không tìm thấy lệnh sort."
        exit 1
    fi
}


check_source_directory() {
    local directory_path="$1"
    local directory_name="$2"

    if [[ ! -d "$directory_path" ]]; then
        print_error "Không tìm thấy thư mục $directory_name: $directory_path"
        exit 1
    fi

    if ! find "$directory_path" \
        -maxdepth 1 \
        -type f \
        -name '*.sql' \
        -print \
        -quit |
        grep -q .; then

        print_error "Thư mục $directory_name không chứa file .sql."
        exit 1
    fi
}


write_sql_header() {
    local output_file="$1"
    local database_name="$2"
    local source_directory="$3"

    cat > "$output_file" <<EOF
-- ============================================================
-- $database_name
-- ============================================================
-- File được tạo tự động bởi build_sql.sh.
--
-- Không chỉnh sửa trực tiếp file này.
-- Hãy chỉnh sửa các file nguồn trong:
--   $source_directory/
--
-- Thời điểm tạo:
--   $(date '+%Y-%m-%d %H:%M:%S %z')
-- ============================================================

PRAGMA foreign_keys = ON;

EOF
}


append_sql_directory() {
    local source_directory="$1"
    local source_directory_name="$2"
    local output_file="$3"

    local file_count=0

    while IFS= read -r -d '' sql_file; do
        local file_name
        local relative_path

        file_name="$(basename -- "$sql_file")"
        relative_path="$source_directory_name/$file_name"

        printf '  Ghép: %s\n' "$relative_path"

        {
            printf '\n'
            printf '%s\n' '-- ============================================================'
            printf '%s\n' "-- BEGIN FILE: $relative_path"
            printf '%s\n' '-- ============================================================'
            printf '\n'

            cat -- "$sql_file"

            # Đảm bảo file kế tiếp không dính vào dòng cuối.
            printf '\n'

            printf '%s\n' '-- ============================================================'
            printf '%s\n' "-- END FILE: $relative_path"
            printf '%s\n' '-- ============================================================'
            printf '\n'
        } >> "$output_file"

        ((file_count += 1))
    done < <(
        find "$source_directory" \
            -maxdepth 1 \
            -type f \
            -name '*.sql' \
            -print0 |
        sort -z -V
    )

    if ((file_count == 0)); then
        print_error "Không có file SQL nào trong $source_directory."
        exit 1
    fi

    printf '  Tổng số file: %d\n' "$file_count"
}


# ============================================================
# Chương trình chính
# ============================================================

check_dependencies

check_source_directory "$SCHEMA_DIR" "schema"
check_source_directory "$INFO_DIR" "info_collected"

printf '%s\n' \
    "============================================" \
    "TẠO DEVICE NETWORK SQL" \
    "============================================"

write_sql_header \
    "$DEVICE_SQL" \
    "DEVICE NETWORK SCHEMA" \
    "schema"

append_sql_directory \
    "$SCHEMA_DIR" \
    "schema" \
    "$DEVICE_SQL"

printf '\n%s\n' \
    "============================================" \
    "TẠO INFO COLLECTED SQL" \
    "============================================"

write_sql_header \
    "$INFO_SQL" \
    "INFO COLLECTED SCHEMA" \
    "info_collected"

append_sql_directory \
    "$INFO_DIR" \
    "info_collected" \
    "$INFO_SQL"

printf '\n%s\n' \
    "============================================" \
    "HOÀN TẤT" \
    "============================================" \
    "Đã tạo:" \
    "  $DEVICE_SQL" \
    "  $INFO_SQL"
