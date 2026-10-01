#!/bin/bash
# 這是對應舊版 Terminal 1 的 ROS2 版本啟動腳本
# 用於啟動 Locobot 的核心驅動 (底盤、手臂、相機)

# 直接在 Container 內部呼叫
if [ -f /workspace/environment.sh ]; then
    source /workspace/environment.sh 150
else
    source /opt/ros/humble/setup.bash
    if [ -f /interbotix_ws/install/setup.bash ]; then
        source /interbotix_ws/install/setup.bash
    fi
    if [ -f /workspace/ros2_ws/install/setup.bash ]; then
        source /workspace/ros2_ws/install/setup.bash
    fi
fi

ARM_REST_SERVICE="/resting"
SHUTTING_DOWN=0
LAUNCH_PID=""
CAMERA_TF_BRIDGE_PID=""
GAMEPAD_MODE_MANAGER_PID=""
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROBOT_MODEL="${ROBOT_MODEL:-locobot_wx200}"
BASE_TYPE="${BASE_TYPE:-kobuki}"
USE_BASE="${USE_BASE:-true}"
USE_CAMERA="${USE_CAMERA:-true}"
USE_RVIZ="${USE_RVIZ:-false}"
RS_CAMERA_ALIGN_DEPTH="${RS_CAMERA_ALIGN_DEPTH:-true}"
MOTOR_CONFIGS="${MOTOR_CONFIGS:-/interbotix_ws/src/interbotix_ros_rovers/interbotix_ros_xslocobots/interbotix_xslocobot_control/config/${ROBOT_MODEL}.yaml}"
MODE_TYPE="${MODE_TYPE:-base}"
GAMEPAD_PARAMS_FILE="${GAMEPAD_PARAMS_FILE:-${SCRIPT_DIR}/teleop_twist_joy_f710.yaml}"
GAMEPAD_DEVICE_ID="${GAMEPAD_DEVICE_ID:-0}"
GAMEPAD_RECORD_SCRIPT="${GAMEPAD_RECORD_SCRIPT:-${SCRIPT_DIR}/record_rosbag.sh}"

if [ "${ROBOT_MODEL}" != "locobot_base" ]; then
    MODE_TYPE="${MODE_TYPE:-all}"
fi

finish_script() {
    local code="$1"
    if [ "${BASH_SOURCE[0]}" != "$0" ]; then
        return "${code}"
    fi
    exit "${code}"
}

call_arm_resting_service() {
    echo "[terminal1] Requesting arm resting pose via ${ARM_REST_SERVICE}..."
    if command -v timeout >/dev/null 2>&1; then
        timeout 8s ros2 service call "${ARM_REST_SERVICE}" std_srvs/srv/Trigger "{}" >/tmp/terminal1_resting.log 2>&1 || true
    else
        ros2 service call "${ARM_REST_SERVICE}" std_srvs/srv/Trigger "{}" >/tmp/terminal1_resting.log 2>&1 || true
    fi
    if grep -q "success: True" /tmp/terminal1_resting.log 2>/dev/null; then
        echo "[terminal1] Arm moved to resting pose."
    else
        echo "[terminal1] Resting pose service unavailable or failed."
    fi
}

cleanup_on_signal() {
    if [ "${SHUTTING_DOWN}" -eq 1 ]; then
        return
    fi
    SHUTTING_DOWN=1

    echo "[terminal1] Shutting down sequence initiated."
    
    if [ "${ROBOT_MODEL}" != "locobot_base" ]; then
        # 【關鍵修改 1】: 強制先停止 Terminal 2 的 vrarm 程式，避免它繼續搶控制權
        echo "[terminal1] Stopping VR arm control (if running) to prevent conflicts..."
        pkill -f "wfh_vr_control vrarm" 2>/dev/null || true

        # 稍微等 1 秒，確保 vrarm 真的停發指令了
        sleep 1

        # 現在安全了，呼叫手臂收回原位的 Service
        call_arm_resting_service
    fi

    # 等手臂收好後，才真正關閉底層的硬體驅動
    if [ -n "${LAUNCH_PID}" ] && kill -0 "${LAUNCH_PID}" 2>/dev/null; then
        kill -INT "${LAUNCH_PID}" 2>/dev/null || true
        wait "${LAUNCH_PID}" 2>/dev/null || true
    fi

    if [ -n "${CAMERA_TF_BRIDGE_PID}" ] && kill -0 "${CAMERA_TF_BRIDGE_PID}" 2>/dev/null; then
        kill -INT "${CAMERA_TF_BRIDGE_PID}" 2>/dev/null || true
        wait "${CAMERA_TF_BRIDGE_PID}" 2>/dev/null || true
    fi

    if [ -n "${GAMEPAD_MODE_MANAGER_PID}" ] && kill -0 "${GAMEPAD_MODE_MANAGER_PID}" 2>/dev/null; then
        kill -INT "${GAMEPAD_MODE_MANAGER_PID}" 2>/dev/null || true
        wait "${GAMEPAD_MODE_MANAGER_PID}" 2>/dev/null || true
    fi

    finish_script 0
}

trap cleanup_on_signal INT TERM

echo "Starting ROS2 Locobot Core Drivers..."
echo "[terminal1] robot_model=${ROBOT_MODEL}"
echo "[terminal1] motor_configs=${MOTOR_CONFIGS}"
echo "[terminal1] rs_camera_align_depth=${RS_CAMERA_ALIGN_DEPTH}"

# 【關鍵修改 2】: 在最後面加上 '&'，讓 launch 在背景執行，這樣我們才能抓到它的 PID 並讓 trap 正常運作
ros2 launch interbotix_xslocobot_control xslocobot_control.launch.py \
    robot_model:="${ROBOT_MODEL}" \
    base_type:="${BASE_TYPE}" \
    use_base:="${USE_BASE}" \
    use_camera:="${USE_CAMERA}" \
    rs_camera_align_depth:="${RS_CAMERA_ALIGN_DEPTH}" \
    rs_rbg_camera_profile:="1280x720x30" \
    rs_depth_module_profile:="1280x720x30" \
    use_rviz:="${USE_RVIZ}" \
    mode_type:="${MODE_TYPE}" \
    motor_configs:="${MOTOR_CONFIGS}" &

LAUNCH_PID=$!

# Start a lightweight service manager. It does not drive the robot until
# /switch_to_gamepad_mode is called.
ros2 run wfh_locobot_control gamepad_mode_manager \
    --ros-args \
    -p params_file:="${GAMEPAD_PARAMS_FILE}" \
    -p joy_device_id:="${GAMEPAD_DEVICE_ID}" \
    -p record_script:="${GAMEPAD_RECORD_SCRIPT}" &
GAMEPAD_MODE_MANAGER_PID=$!

# 檢查 Docker image 是否存在，若不存在則進行 build
if [[ "$(docker images -q locobot_humble_dev 2> /dev/null)" == "" ]]; then
    echo "Image not found. Building docker image..."
    docker compose -f docker-compose.locobot.yml build
else
    echo "Image found. Skipping build."
fi

# 檢查 Container 是否已經在執行，如果沒有就用 up -d 啟動在背景，如果已啟動就直接 exec 進去
if [ "$(docker ps -q -f name=locobot_humble_dev)" ]; then
    echo "Container is running. Executing bash..."
    docker exec -it locobot_humble_dev /bin/bash
else
    echo "Starting container and executing bash..."
    docker compose -f docker-compose.locobot.yml up -d
    docker exec -it locobot_humble_dev /bin/bash
fi

wait "${LAUNCH_PID}"
LAUNCH_EXIT_CODE=$?

if [ -n "${CAMERA_TF_BRIDGE_PID}" ] && kill -0 "${CAMERA_TF_BRIDGE_PID}" 2>/dev/null; then
    kill -INT "${CAMERA_TF_BRIDGE_PID}" 2>/dev/null || true
    wait "${CAMERA_TF_BRIDGE_PID}" 2>/dev/null || true
fi

if [ -n "${GAMEPAD_MODE_MANAGER_PID}" ] && kill -0 "${GAMEPAD_MODE_MANAGER_PID}" 2>/dev/null; then
    kill -INT "${GAMEPAD_MODE_MANAGER_PID}" 2>/dev/null || true
    wait "${GAMEPAD_MODE_MANAGER_PID}" 2>/dev/null || true
fi

finish_script "${LAUNCH_EXIT_CODE}"
