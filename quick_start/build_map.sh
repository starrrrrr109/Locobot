#!/bin/bash

# 當使用者按下 Ctrl+C 時，自動結束所有背景程序
trap "echo -e '\n正在關閉所有服務...'; kill 0" EXIT

echo "=========================================="
echo " 🚀 啟動 Static TF Bridge + foxglove_bridge + RTAB-Map SLAM "
echo "=========================================="

echo "[1/3] 建立相機與底盤間的 TF 橋樑 (連結 locobot/camera_locobot_link -> camera_link)..."
# 位置完全重疊，將 RealSense 根節點接上 LoCoBot 的雲台相機接點
ros2 run tf2_ros static_transform_publisher \
    --x 0.0 --y 0.0 --z 0.0 \
    --yaw 0.0 --pitch 0.0 --roll 0.0 \
    --frame-id locobot/camera_locobot_link \
    --child-frame-id camera_link &
sleep 2

echo "[2/3] 啟動 RTAB-Map SLAM..."
ros2 launch rtabmap_launch rtabmap.launch.py \
    rtabmap_args:="--delete_db_on_start" \
    subscribe_depth:=true \
    rgb_topic:=/mast3r/camera/color/image_raw \
    depth_topic:=/mast3r/camera/depth/image_rect_raw \
    camera_info_topic:=/mast3r/camera/color/camera_info \
    depth_camera_info_topic:=/mast3r/camera/depth/camera_info \
    frame_id:=locobot/base_link \
    odom_frame_id:=locobot/odom \
    odom_topic:=/locobot/odom \
    approx_sync:=true \
    visual_odometry:=false \
    rtabmap_viz:=false \
    qos:=1 &
sleep 3

echo "[3/3] 啟動 Foxglove Bridge (WebSocket: 8765)..."
ros2 launch foxglove_bridge foxglove_bridge_launch.xml &
sleep 2

echo "=========================================="
echo " ✅ 所有系統已就緒！"
echo " 📱 請在筆電開啟 Foxglove Studio 連線至 ws://localhost:8765"
echo " 💡 按下 [Ctrl + C] 可結束所有背景程式"
echo "=========================================="

wait