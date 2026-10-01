#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
STAMP="$(date +%m%d_%H%M)"
BAG_DIR="${SCRIPT_DIR}/bags/${STAMP}"

source /opt/ros/humble/setup.bash
if [ -f /interbotix_ws/install/setup.bash ]; then
    source /interbotix_ws/install/setup.bash
fi
if [ -f /workspace/ros2_ws/install/setup.bash ]; then
    source /workspace/ros2_ws/install/setup.bash
fi

mkdir -p "${BAG_DIR}"

ros2 bag record -o "${BAG_DIR}/vr" --max-bag-size 2147483648 \
    /locobot/joint_states \
    /locobot/gripper/state \
    /tf \
    /tf_static