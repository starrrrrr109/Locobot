#!/bin/bash
# Start triple-camera image fusion publisher.

source /opt/ros/humble/setup.bash
if [ -f /workspace/ros2_ws/install/setup.bash ]; then
    source /workspace/ros2_ws/install/setup.bash
fi

echo "Starting camera fusion node..."
ros2 run wfh_vr_control camera_fusion \
    --ros-args \
    -p camera1_topic:=/camera_1/camera/color/image_raw \
    -p camera2_topic:=/camera_2/camera/color/image_raw \
    -p camera3_topic:=/camera_3/camera/color/image_raw \
    -p output_topic:=/locobot/camera/camera/color/image_raw/compressed/fusion \
    -p overlap_px:=80 \
    -p sync_slop_sec:=0.03
