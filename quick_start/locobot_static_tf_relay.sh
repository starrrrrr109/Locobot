#!/bin/bash
# Relay only the Locobot base static TF edges needed by Stretch alignment.

set -e

if [ -f /workspace/environment.sh ]; then
    source /workspace/environment.sh 100
else
    source /opt/ros/humble/setup.bash
    if [ -f /interbotix_ws/install/setup.bash ]; then
        source /interbotix_ws/install/setup.bash
    fi
    if [ -f /workspace/ros2_ws/install/setup.bash ]; then
        source /workspace/ros2_ws/install/setup.bash
    fi
fi

echo "Starting filtered Locobot static TF relay..."
echo "  /tf_static -> /locobot/static_tf_relay"
echo "  locobot/base_footprint -> locobot/base_link"
echo "  locobot/base_link -> locobot/apriltag_link"

ros2 launch wfh_locobot_control locobot_static_tf_relay.launch.py
