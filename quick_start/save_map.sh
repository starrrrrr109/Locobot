#!/bin/bash

MAP_DIR="/workspace/maps"
MAP_NAME="my_rgbd_map"
DB_PATH="$HOME/.ros/rtabmap.db"

source /opt/ros/humble/setup.bash
if [ -f /workspace/install/setup.bash ]; then
    source /workspace/install/setup.bash
elif [ -f ~/ros2_ws/install/setup.bash ]; then
    source ~/ros2_ws/install/setup.bash
fi

mkdir -p "$MAP_DIR"

echo "=========================================="
echo "💾 [1/2] 正在備份 3D 數據庫與導出 3D 點雲..."
echo "=========================================="

if [ -f "$DB_PATH" ]; then
    # 複製 .db 數據庫
    cp "$DB_PATH" "$MAP_DIR/${MAP_NAME}.db"
    echo "✅ 已備份完整數據庫至：$MAP_DIR/${MAP_NAME}.db"

    # 導出 3D .ply 點雲檔
    echo "📦 正在導出 3D PLY 點雲..."
    rtabmap-export --ply "$MAP_DIR/${MAP_NAME}.db" > /dev/null 2>&1
    
    # 重新命名與搬移
    if [ -f "${MAP_NAME}_cloud.ply" ]; then
        mv "${MAP_NAME}_cloud.ply" "$MAP_DIR/${MAP_NAME}.ply"
    elif [ -f "${MAP_NAME}.ply" ]; then
        mv "${MAP_NAME}.ply" "$MAP_DIR/${MAP_NAME}.ply"
    fi
    echo "✅ 3D 點雲檔案已存至：$MAP_DIR/${MAP_NAME}.ply"
else
    echo "❌ 找不到 $DB_PATH，請確認 RTAB-Map 是否有在運行。"
    exit 1
fi

echo ""
echo "=========================================="
echo "💾 [2/2] 正在生成 2D 導航地圖 (.yaml / .pgm)..."
echo "=========================================="

# 方式 A：直接從 .db 數據庫導出 2D 格點地圖（最穩定、不依賴網路）
echo "⚙️ 正在從 .db 數據庫提取 2D 格點地圖..."
rtabmap-export --grid "$MAP_DIR/${MAP_NAME}.db" > /dev/null 2>&1

# 檢查導出檔名並整理
if [ -f "${MAP_NAME}_map.pgm" ]; then
    mv "${MAP_NAME}_map.pgm" "$MAP_DIR/${MAP_NAME}.pgm"
    mv "${MAP_NAME}_map.yaml" "$MAP_DIR/${MAP_NAME}.yaml"
    echo "✅ 2D 地圖導出成功！（已從 .db 自動生成）"
else
    # 方式 B：備用方案，嘗試從線上 Topic (/map) 抓取
    echo "⚠️ .db 導出未成功，嘗試透過 ros2 map_saver 抓取 /map..."
    ros2 run nav2_map_server map_saver_cli \
        -f "$MAP_DIR/$MAP_NAME" \
        -t /map \
        --ros-args -p map_subscribe_transient_local:=false
fi

echo ""
echo "=========================================="
echo " 🎉 所有地圖儲存完成！"
echo " 📁 檔案列表 ($MAP_DIR):"
ls -lh "$MAP_DIR"/${MAP_NAME}*
echo "=========================================="