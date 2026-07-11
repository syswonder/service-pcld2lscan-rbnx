#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""pcld2lscan-rbnx — atlas bridge (driver-init lifecycle).

Converts a 3D PointCloud2 topic (``robonix/primitive/lidar/lidar3d``)
into a 2D LaserScan topic (``robonix/service/lidar/scan_converter/scan``),
wrapping the system-installed ``pointcloud_to_laserscan_node``.

Spawn order:
  1. ``start.sh`` launches THIS process via ``python3 -m
     pcld2lscan_rbnx.atlas_bridge``.
  2. ``Service.run()`` opens the MCP HTTP server, registers the cap on atlas,
     and blocks awaiting ``Driver(CMD_INIT, config_json)``.
  3. ``rbnx boot`` calls Driver(CMD_INIT). The ``@service.on_init`` handler
     resolves the upstream lidar3d topic from atlas, spawns
     ``pointcloud_to_laserscan_node`` with remapped topics, waits for the
     LaserScan output to appear, and declares the scan contract on atlas.
  4. No MCP tools — this is a pure data-flow service. Downstream consumers
     discover the scan output via ``robonix/service/lidar/scan_converter/scan``.

Config (passed via ``Driver(CMD_INIT, config_json)``):
    scan_frame       default "scanner"     — target frame for output LaserScan
    scan_rate_hz     default 10.0          — desired scan rate
    scan_timeout_s   default 15.0          — wait for scan output topic
    topic_remap      dict — per-key override (cloud_in, scan, etc.)
"""
from __future__ import annotations

import json
import logging
import math
import os
import signal
import subprocess
import threading
import time
from pathlib import Path

from robonix_api import ATLAS, Service, Ok, Err, Deferred

log = logging.getLogger("pcld2lscan")

svc = Service(
    id=os.environ.get("ROBONIX_CAPABILITY_ID", "pcld2lscan"),
    namespace="robonix/service/lidar/scan_converter",
)

# ── shared state ─────────────────────────────────────────────────────────────
_pkg_root: Path = Path(__file__).resolve().parent.parent
_convert_proc: "subprocess.Popen | None" = None
_initialized = False


# ── atlas-driven dependency discovery ────────────────────────────────────────
def _resolve_dep(contract_id: str) -> str | None:
    """Query atlas for a contract over ROS2; return endpoint topic or None."""
    try:
        caps = ATLAS.find_capability(contract_id=contract_id, transport="ros2")
    except Exception:
        return None
    if not caps:
        return None
    try:
        ch = svc.connect_capability(caps[0], contract_id, "ros2")
    except Exception:
        return None
    ep = ch.endpoint
    try:
        ch.close()
    except Exception:
        pass
    return ep or None


def _build_remap_args(cfg: dict) -> tuple[list[str], list[str]]:
    """Resolve cloud_in topic from atlas, build remap args and output topic."""
    overrides = dict(cfg.get("topic_remap", {}) or {})
    remap_args: list[str] = []
    missing: list[str] = []

    # Input: lidar3d (PointCloud2)
    cloud_topic = overrides.get("cloud_in", "") or \
                  _resolve_dep("robonix/primitive/lidar/lidar3d") or ""
    if not cloud_topic:
        missing.append("robonix/primitive/lidar/lidar3d")
    else:
        remap_args.append(f"cloud_in:={cloud_topic}")
        log.info("resolved lidar3d = %s", cloud_topic)

    # Output scan topic (we'll derive it or use explicit)
    scan_frame = cfg.get("scan_frame", "scanner")
    remap_args.append(f"scan:=/scanner/scan")

    # Store params for spawning
    remap_args.append(f"target_frame:={scan_frame}")

    return remap_args, missing


# ── pointcloud_to_laserscan subprocess management ────────────────────────────
def _spawn_converter(remap_args: list[str]) -> None:
    """Spawn pointcloud_to_laserscan_node matching sample launch exactly."""
    global _convert_proc

    # Parse remap args into ros2 run params
    cloud_in = "/scanner/cloud"
    scan_out = "/scanner/scan"
    target_frame = "livox_frame"
    for r in remap_args:
        k, v = r.split(":=", 1)
        if k == "cloud_in":
            cloud_in = v
        elif k == "scan":
            scan_out = v
        elif k == "target_frame":
            target_frame = v

    args = [
        "ros2", "run", "pointcloud_to_laserscan", "pointcloud_to_laserscan_node",
        "--ros-args",
        "-r", f"cloud_in:={cloud_in}",
        "-r", f"scan:={scan_out}",
        "-r", "__node:=pointcloud_to_laserscan_rbnx",
        "-p", f"target_frame:={target_frame}",
        "-p", "transform_tolerance:=0.01",
        "-p", "min_height:=0.05",
        "-p", "max_height:=1.0",
        "-p", f"angle_min:={math.radians(-179.0)}",
        "-p", f"angle_max:={math.radians(180.0)}",
        "-p", "angle_increment:=0.0087",
        "-p", "scan_time:=0.2",
        "-p", "range_min:=0.03",
        "-p", "range_max:=20.0",
        "-p", "use_inf:=True",
        "-p", "inf_epsilon:=1.0",
    ]

    log_path = _pkg_root / "rbnx-build" / "data" / "pcld2lscan.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_fh = open(log_path, "ab", buffering=0)
    log.info("spawning pointcloud_to_laserscan (cloud_in=%s, scan=%s) → %s",
             cloud_in, scan_out, log_path)
    _convert_proc = subprocess.Popen(
        args, stdout=log_fh, stderr=log_fh, start_new_session=True,
    )


def _kill_converter() -> None:
    p = _convert_proc
    if p is None or p.poll() is not None:
        return
    try:
        os.killpg(os.getpgid(p.pid), signal.SIGTERM)
    except ProcessLookupError:
        return
    try:
        p.wait(timeout=5.0)
    except subprocess.TimeoutExpired:
        try:
            os.killpg(os.getpgid(p.pid), signal.SIGKILL)
        except ProcessLookupError:
            pass


# ── lifecycle ────────────────────────────────────────────────────────────────
@svc.on_init
def init(cfg):
    """Driver(CMD_INIT). Resolve atlas deps, spawn converter, wait for scan."""
    global _initialized
    with threading.Lock():
        if _initialized:
            return Ok()

    cfg = cfg or {}
    if isinstance(cfg, str):
        try:
            cfg = json.loads(cfg) if cfg else {}
        except json.JSONDecodeError as e:
            return Err(f"bad config_json: {e}")

    scan_timeout = float(cfg.get("scan_timeout_s", 15.0))

    remap_args, missing = _build_remap_args(cfg)
    if missing:
        return Deferred(
            f"missing required atlas contracts: {missing} "
            "(awaiting upstream provider)"
        )

    try:
        _spawn_converter(remap_args)
    except Exception as e:
        return Err(f"spawn pointcloud_to_laserscan failed: {e}")

    # Wait for the output scan topic to appear
    scan_topic = "/scanner/scan"
    deadline = time.monotonic() + scan_timeout
    found = False
    while time.monotonic() < deadline:
        try:
            # Use ros2 topic list to check
            result = subprocess.run(
                ["ros2", "topic", "list"],
                capture_output=True, text=True, timeout=5.0,
            )
            if scan_topic in result.stdout.splitlines():
                found = True
                break
        except Exception:
            pass
        time.sleep(1.0)

    if not found:
        _kill_converter()
        return Err(f"scan topic {scan_topic} did not appear within {scan_timeout:.1f}s")

    # Declare the output scan contract on atlas
    svc.declare_ros2_topic(
        "robonix/service/lidar/scan_converter/scan",
        scan_topic,
        qos="best_effort",
        description="Converted LaserScan from PointCloud2",
    )

    with threading.Lock():
        _initialized = True
    log.info("init complete: conversion active, scan=%s declared on atlas",
             scan_topic)
    return Ok()


def _on_signal(signum, _frame):
    log.info("signal %d — shutting down", signum)
    _kill_converter()
    raise SystemExit(0)


def main() -> int:
    signal.signal(signal.SIGTERM, _on_signal)
    signal.signal(signal.SIGINT, _on_signal)
    try:
        svc.run()
    finally:
        _kill_converter()
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
