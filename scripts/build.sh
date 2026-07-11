#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
# Build phase: rbnx codegen + colcon build for pointcloud_to_laserscan.
set -euo pipefail
PKG="${RBNX_PACKAGE_ROOT:-$(cd "$(dirname "$0")/.." && pwd)}"
cd "$PKG"
CLEAN="${RBNX_BUILD_CLEAN:-}"

if [[ "$CLEAN" == "1" ]]; then
    echo "[pcld2lscan/build] clean: removing rbnx-build/"
    rm -rf rbnx-build
fi
mkdir -p rbnx-build/data

# Sanity check
if ! ros2 pkg list 2>/dev/null | grep -q "^pointcloud_to_laserscan$"; then
    echo "[pcld2lscan/build] NOTE: pointcloud_to_laserscan not found system-wide."
    echo "                     Building from vendored source at src/pointcloud_to_laserscan"
fi

# Build the vendored pointcloud_to_laserscan package if source exists
ROS_SRC="$PKG/src/pointcloud_to_laserscan"
if [ -d "$ROS_SRC" ] && command -v colcon >/dev/null 2>&1; then
    echo "[pcld2lscan/build] building pointcloud_to_laserscan from source"
    BUILD_WS="$(dirname "$ROS_SRC")"
    pushd "$BUILD_WS" >/dev/null
    colcon build --merge-install --packages-select pointcloud_to_laserscan
    popd >/dev/null
    echo "[pcld2lscan/build] ROS2 build done."
fi

# rbnx codegen
FLAGS=(--out-dir "$PKG/rbnx-build/codegen" --mcp)
[[ "$CLEAN" == "1" ]] && FLAGS+=(--clean)
echo "[pcld2lscan/build] rbnx codegen ${FLAGS[*]}"
rbnx codegen -p "$PKG" "${FLAGS[@]}"

touch "$PKG/rbnx-build/.rbnx-built"
echo "[pcld2lscan/build] done."
