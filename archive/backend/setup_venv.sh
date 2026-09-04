#!/usr/bin/env bash
# =============================================================================
# setup_venv.sh — Tạo .venv bằng uv và cài thư viện từ file text
# Cách dùng: bash setup_venv.sh [packages_file] [venv_dir]
#   packages_file : file text chứa tên thư viện (mặc định: packages.txt)
#   venv_dir      : thư mục venv sẽ tạo    (mặc định: .venv)
# =============================================================================

set -euo pipefail

# ---------- Tham số đầu vào --------------------------------------------------
PACKAGES_FILE="${1:-packages.txt}"
VENV_DIR="${2:-.venv}"
OUTPUT_FILE="venv_path.txt"

# ---------- Kiểm tra file packages -------------------------------------------
if [[ ! -f "$PACKAGES_FILE" ]]; then
  echo "[LỖI] Không tìm thấy file thư viện: '$PACKAGES_FILE'"
  echo "       Tạo file '$PACKAGES_FILE' với mỗi tên thư viện trên một dòng."
  exit 1
fi

echo "============================================="
echo "  UV VENV SETUP"
echo "============================================="
echo "[1/4] Kiểm tra uv..."
if ! command -v uv &>/dev/null; then
  echo "[LỖI] Không tìm thấy 'uv'. Cài đặt tại: https://docs.astral.sh/uv/"
  exit 1
fi
echo "      uv version: $(uv --version)"

# ---------- Tạo virtual environment -----------------------------------------
echo "[2/4] Tạo virtual environment tại: $VENV_DIR"
uv venv "$VENV_DIR"

# ---------- Lấy đường dẫn tuyệt đối -----------------------------------------
VENV_ABS="$(cd "$VENV_DIR" && pwd)"
PYTHON_BIN="$VENV_ABS/bin/python"

# ---------- Cài thư viện từ file ---------------------------------------------
echo "[3/4] Cài thư viện từ file: $PACKAGES_FILE"
echo "----------------------------------------------"

# Lọc dòng trống và comment (#)
PACKAGES=()
while IFS= read -r line || [[ -n "$line" ]]; do
  # Bỏ khoảng trắng đầu/cuối
  line="${line#"${line%%[![:space:]]*}"}"
  line="${line%"${line##*[![:space:]]}"}"
  # Bỏ qua dòng trống và dòng comment
  [[ -z "$line" || "$line" == \#* ]] && continue
  PACKAGES+=("$line")
done < "$PACKAGES_FILE"

if [[ ${#PACKAGES[@]} -eq 0 ]]; then
  echo "[CẢNH BÁO] File '$PACKAGES_FILE' không có thư viện nào (sau khi lọc comment)."
else
  echo "  Thư viện sẽ cài: ${PACKAGES[*]}"
  uv pip install --python "$PYTHON_BIN" "${PACKAGES[@]}"
fi

echo "----------------------------------------------"

# ---------- Xuất đường dẫn venv ra file -------------------------------------
echo "[4/4] Ghi đường dẫn venv vào: $OUTPUT_FILE"
echo "$VENV_ABS" > "$OUTPUT_FILE"

# ---------- Kiểm tra package ↔ import ----------------------------------------
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CHECK_SCRIPT="$SCRIPT_DIR/script/check_packages_imports.py"
if [[ -f "$CHECK_SCRIPT" ]]; then
  echo ""
  echo "[5/5] Kiểm tra package ↔ import..."
  "$PYTHON_BIN" "$CHECK_SCRIPT" --packages "$PACKAGES_FILE" || true
fi

echo ""
echo "============================================="
echo "  HOÀN THÀNH!"
echo "============================================="
echo "  Venv   : $VENV_ABS"
echo "  Python : $PYTHON_BIN"
echo "  Đường dẫn đã lưu tại: $OUTPUT_FILE"
echo ""
echo "  Chạy script Python bằng venv:"
echo "    $PYTHON_BIN your_script.py"
echo ""
echo "  Hoặc kích hoạt venv thủ công:"
echo "    source $VENV_ABS/bin/activate"
echo "============================================="
