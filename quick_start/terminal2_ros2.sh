#!/bin/bash
# 這是對應舊版 Terminal 2 的 ROS2 版本啟動腳本
# 用於啟動 VR 手臂與底盤控制相關，等同於原本的 vrarm.py
# (若你將 VR 控制分拆，請根據實際的 Node 名稱微調)

source /opt/ros/humble/setup.bash
if [ -f /interbotix_ws/install/setup.bash ]; then
    source /interbotix_ws/install/setup.bash
fi
if [ -f /workspace/ros2_ws/install/setup.bash ]; then
    source /workspace/ros2_ws/install/setup.bash
fi

export LOCOBOT_ARM_MODEL=locobot_wx200
export LOCOBOT_MOBILE_ARM_MODEL=mobile_wx200

# 假設與 terminal3_ros2.sh 同邏輯 (或其他特定 node)
echo "Starting ROS2 VR Control..."
ros2 run wfh_vr_control vrarm
