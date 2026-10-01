#!/bin/bash
set -e

source /opt/ros/humble/setup.bash
if [ -f /interbotix_ws/install/setup.bash ]; then
    source /interbotix_ws/install/setup.bash
fi
if [ -f /workspace/ros2_ws/install/setup.bash ]; then
    source /workspace/ros2_ws/install/setup.bash
fi

echo "Publishing camera home command to /locobot/commands/joint_group..."
ros2 topic pub --once /locobot/commands/joint_group interbotix_xs_msgs/msg/JointGroupCommand "{name: camera, cmd: [0.0, 0.0]}"
