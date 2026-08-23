#!/usr/bin/env bash
set -euo pipefail

source_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
app_dir="$(cd "${source_dir}/../.." && pwd)"
build_dir="${app_dir}/build/syslog_collector"
cache_dir="${TMPDIR:-/tmp}/networktools-ccache"
mkdir -p "${cache_dir}"
export CCACHE_DIR="${cache_dir}"

cmake --fresh -S "${source_dir}" -B "${build_dir}" -DCMAKE_BUILD_TYPE=Release
cmake --build "${build_dir}" --parallel
cmake --install "${build_dir}" --prefix "${app_dir}"
