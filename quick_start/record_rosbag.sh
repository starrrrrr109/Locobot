#!/bin/bash

# Load ROS environment (required inside the container)
source /workspace/environment.sh 150

set -euo pipefail

# Optional: allow overriding output directory/name via env vars
BAG_DIR=${BAG_DIR:-/workspace/rosbags}
BAG_NAME=${BAG_NAME:-locobot_$(date +%Y%m%d_%H%M%S)}

mkdir -p "$BAG_DIR"

echo "Recording rosbag to ${BAG_DIR}/${BAG_NAME}"
ros2 bag record -o "${BAG_DIR}/${BAG_NAME}" \
  /locobot/camera/camera/aligned_depth_to_color/image_raw/compressedDepth \
  /locobot/camera/camera/aligned_depth_to_color/image_raw/compressedDepth/relay \
  /locobot/camera/camera/color/camera_info \
  /locobot/camera/camera/color/image_raw/compressed \
  /locobot/camera/camera/color/image_raw/compressed/relay \
  /locobot/camera/camera/color/image_raw/compressedDepth \
  /locobot/camera/camera/depth/camera_info \
  /locobot/camera_pose_odom \
  /locobot/commands/velocity \
  /locobot/odom \
  /locobot/robot_description \
  /tf \
  /tf_static