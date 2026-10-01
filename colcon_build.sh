#!/bin/bash
set -eo pipefail

source /opt/ros/humble/setup.bash

cd /workspace/ros2_ws || exit 1

# ament_cmake_python expects this generated Python package to be a symlink when
# using --symlink-install. A previous non-symlink or interrupted build can leave
# a real directory here, which CMake cannot replace with a symlink.
APRILTAG_PYTHON_LINK="build/apriltag_msgs/ament_cmake_python/apriltag_msgs/apriltag_msgs"
if [ -d "${APRILTAG_PYTHON_LINK}" ] && [ ! -L "${APRILTAG_PYTHON_LINK}" ]; then
    echo "Removing stale apriltag_msgs build directory: ${APRILTAG_PYTHON_LINK}"
    rm -rf -- "${APRILTAG_PYTHON_LINK}"
fi

REALSENSE_LINK_FILE="build/realsense2_camera/CMakeFiles/realsense2_camera.dir/link.txt"
if [ -f "${REALSENSE_LINK_FILE}" ]; then
    stale_realsense_lib="$(grep -o '/[^ ]*/librealsense2\.so\.[^ ]*' "${REALSENSE_LINK_FILE}" | while read -r lib; do
        if [ ! -e "${lib}" ]; then
            printf '%s\n' "${lib}"
            break
        fi
    done)"
    if [ -n "${stale_realsense_lib}" ]; then
        echo "Removing stale realsense2_camera build cache: ${stale_realsense_lib} is missing"
        rm -rf -- build/realsense2_camera
    fi
fi

colcon build --symlink-install
source install/setup.bash
echo "ROS2 Workspace build completed successfully."
