#!/bin/bash

# ==========================================
# 1. 載入 ROS 2 系統與工作空間環境變數
# ==========================================
source /opt/ros/humble/setup.bash
source /workspace/install/setup.bash
export ROS_DOMAIN_ID=150
export ROS_LOCALHOST_ONLY=0

# ==========================================
# 3. 依序啟動節點 (使用 & 讓指令在背景執行)
# ==========================================
echo "🚀 [1/2] 正在啟動 joy_node..."
ros2 run joy joy_node \
	--ros-args \
	--params-file /workspace/quick_start/teleop_twist_joy_f710.yaml &

# 稍微等待 1 秒，確保第一個節點初始化成功
sleep 1
wait
