#!/bin/bash
# ROS2 TF relay script
# Relays /tf -> /locobot/tf and /tf_static -> /locobot/tf_static

source /opt/ros/humble/setup.bash
if [ -f /interbotix_ws/install/setup.bash ]; then
    source /interbotix_ws/install/setup.bash
fi
if [ -f /workspace/ros2_ws/install/setup.bash ]; then
    source /workspace/ros2_ws/install/setup.bash
fi

echo "Starting TF relay..."
ros2 run wfh_locobot_control tf_relay_node.py
