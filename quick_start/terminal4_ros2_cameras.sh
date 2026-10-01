#!/bin/bash
# Start three RealSense cameras in a dedicated terminal.
# Fill serial_no_{1,2,3} with your own camera serial numbers.

source /opt/ros/humble/setup.bash
if [ -f /workspace/ros2_ws/install/setup.bash ]; then
    source /workspace/ros2_ws/install/setup.bash
fi

echo "Starting three RealSense cameras (640x480x30, align depth to color)..."
ros2 launch wfh_locobot_control triple_camera.launch.py \
    serial_no_1:=CAM1_SERIAL_HERE \
    serial_no_2:=CAM2_SERIAL_HERE \
    serial_no_3:=CAM3_SERIAL_HERE \
    inter_cam_sync_mode_1:=0 \
    inter_cam_sync_mode_2:=0 \
    inter_cam_sync_mode_3:=0
