#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
# Start the atlas bridge. NO conversion node spawn here — the
# pointcloud_to_laserscan_node runs inside Driver(CMD_INIT).
set -euo pipefail
PKG="${RBNX_PACKAGE_ROOT:-$(cd "$(dirname "$0")/.." && pwd)}"
cd "$PKG"

ROS_DISTRO="${ROS_DISTRO:-humble}"
set +u; source "/opt/ros/${ROS_DISTRO}/setup.bash"; set -u

# Source vendored ROS2 package install if present
ROS_INSTALL="$PKG/install"
if [ -f "$ROS_INSTALL/setup.bash" ]; then
    set +u; source "$ROS_INSTALL/setup.bash"; set -u
    source install/setup.bash
fi

export PYTHONPATH="$PKG/rbnx-build/codegen/proto_gen:$PKG/rbnx-build/codegen/robonix_mcp_types:$PKG:${PYTHONPATH:-}"
if ROBONIX_API="$(rbnx path robonix-api 2>/dev/null)"; then
    export PYTHONPATH="$ROBONIX_API:$PYTHONPATH"
fi

exec python3 -m pcld2lscan_rbnx.atlas_bridge
