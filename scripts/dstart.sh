#!/usr/bin/env bash
# Debug: manually launch pointcloud_to_laserscan for testing.
# Adjust topics/params as needed.
cd /home/sunrise/cxk/lite3_rbnx_ws/services/pcld2lscan-rbnx/src
source install/setup.bash 
ros2 launch pointcloud_to_laserscan sample_pointcloud_to_laserscan_launch.py
