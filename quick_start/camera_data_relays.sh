#!/bin/bash
# Publish throttled camera relay topics and the camera pose in odom.

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

set -euo pipefail

RELAY_FPS="${RELAY_FPS:-6.0}"
COLOR_INPUT="/locobot/camera/camera/color/image_raw/compressed"
COLOR_OUTPUT="${COLOR_INPUT}/relay"
DEPTH_INPUT="/locobot/camera/camera/aligned_depth_to_color/image_raw/compressedDepth"
DEPTH_OUTPUT="${DEPTH_INPUT}/relay"
PIDS=()

cleanup() {
    exit_code=$?
    trap - EXIT INT TERM

    echo
    echo "Stopping camera relay nodes..."
    for pid in "${PIDS[@]}"; do
        if kill -0 "${pid}" 2>/dev/null; then
            # Each command runs in its own process group. Signal the whole group
            # so ros2 CLI wrappers cannot leave their child nodes behind.
            kill -INT -- "-${pid}" 2>/dev/null || true
        fi
    done
    for pid in "${PIDS[@]}"; do
        wait "${pid}" 2>/dev/null || true
    done

    exit "${exit_code}"
}

color_publishers="$(ros2 topic info "${COLOR_OUTPUT}" 2>/dev/null | awk '/Publisher count:/ {print $3}' || true)"
depth_publishers="$(ros2 topic info "${DEPTH_OUTPUT}" 2>/dev/null | awk '/Publisher count:/ {print $3}' || true)"
pose_node_running=false
if ros2 node list 2>/dev/null | grep -Fxq "/camera_pose_odom_relay"; then
    pose_node_running=true
fi

if [ "${color_publishers:-0}" -gt 0 ] || [ "${depth_publishers:-0}" -gt 0 ] || [ "${pose_node_running}" = true ]; then
    echo "A camera relay is already running; refusing to create duplicate publishers." >&2
    echo "Stop the existing relay terminal first, then run this script again." >&2
    echo "  color relay publishers: ${color_publishers:-0}" >&2
    echo "  depth relay publishers: ${depth_publishers:-0}" >&2
    echo "  camera_pose_odom_relay running: ${pose_node_running}" >&2
    exit 1
fi

trap cleanup EXIT INT TERM

echo "Starting camera topic throttles at ${RELAY_FPS} FPS..."
echo "  ${COLOR_INPUT}"
echo "    -> ${COLOR_OUTPUT}"
echo "  ${DEPTH_INPUT}"
echo "    -> ${DEPTH_OUTPUT}"

setsid ros2 run topic_tools throttle messages \
    --ros-args \
    -r __node:=locobot_color_image_throttle \
    -p input_topic:="${COLOR_INPUT}" \
    -p output_topic:="${COLOR_OUTPUT}" \
    -p msgs_per_sec:="${RELAY_FPS}" \
    -p use_wall_clock:=true &
PIDS+=("$!")

setsid ros2 run topic_tools throttle messages \
    --ros-args \
    -r __node:=locobot_depth_image_throttle \
    -p input_topic:="${DEPTH_INPUT}" \
    -p output_topic:="${DEPTH_OUTPUT}" \
    -p msgs_per_sec:="${RELAY_FPS}" \
    -p use_wall_clock:=true &
PIDS+=("$!")

echo "Starting camera pose odom relay..."
setsid ros2 launch wfh_locobot_control camera_pose_odom_relay.launch.py &
PIDS+=("$!")

echo "All camera relay nodes are running. Press Ctrl+C to stop them."

set +e
wait -n "${PIDS[@]}"
wait_status=$?
set -e

if [ "${wait_status}" -eq 0 ]; then
    echo "A camera relay process exited; stopping the remaining nodes."
    exit 1
fi
exit "${wait_status}"
