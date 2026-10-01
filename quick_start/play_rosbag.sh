#!/bin/bash

set -eo pipefail

CONTAINER_NAME="${CONTAINER_NAME:-locobot_humble_dev}"
HOST_WORKSPACE="${HOST_WORKSPACE:-/home/locobot/WFH_locobot_20260317}"
CONTAINER_WORKSPACE="${CONTAINER_WORKSPACE:-/workspace}"
# DEFAULT_BAG_NAME="${DEFAULT_BAG_NAME:-locobot_20260705_064548}"

DEFAULT_BAG_NAME="${DEFAULT_BAG_NAME:-locobot_20260816_063109}"
# 124348是黑布

IN_CONTAINER=0

usage() {
    cat <<EOF
Usage:
  $0 [options] [bag_name_or_path] [-- ros2 bag play args]

Options:
  -l, --list        List available rosbags and exit
  -h, --help        Show this help

Environment:
  BAG_DIR           Rosbag directory inside the container (default: /workspace/rosbags)
  DEFAULT_BAG_NAME  Default bag to play when no bag argument is given
  CONTAINER_NAME    Docker container name (default: locobot_humble_dev)
  USE_REMAP         Set to 1 to enable the REMAP_RULES below (default: 0)

Examples:
  $0
  $0 --list
  $0 locobot_20260530_141100
  $0 /workspace/rosbags/locobot_20260530_141100 -- --loop --rate 0.5
  USE_REMAP=1 $0 locobot_20260530_070325
EOF
}

quote_args() {
    local quoted=()
    local arg
    for arg in "$@"; do
        quoted+=("$(printf '%q' "$arg")")
    done
    printf '%s ' "${quoted[@]}"
}

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
    usage
    exit 0
fi

if [[ "${1:-}" == "--inside-container" ]]; then
    IN_CONTAINER=1
    shift
elif [[ -f "${CONTAINER_WORKSPACE}/environment.sh" ]]; then
    IN_CONTAINER=1
fi

if [[ "$IN_CONTAINER" -eq 0 ]]; then
    DOCKER_ENV_ARGS=()
    if [[ -n "${BAG_DIR+x}" ]]; then
        DOCKER_ENV_ARGS+=("-e" "BAG_DIR=${BAG_DIR}")
    fi
    if [[ -n "${DEFAULT_BAG_NAME+x}" ]]; then
        DOCKER_ENV_ARGS+=("-e" "DEFAULT_BAG_NAME=${DEFAULT_BAG_NAME}")
    fi
    if [[ -n "${USE_REMAP+x}" ]]; then
        DOCKER_ENV_ARGS+=("-e" "USE_REMAP=${USE_REMAP}")
    fi

    if ! command -v docker >/dev/null 2>&1; then
        echo "docker command not found. Please run this script inside ${CONTAINER_NAME}." >&2
        exit 1
    fi

    if ! docker ps -q -f "name=${CONTAINER_NAME}" | grep -q .; then
        echo "Container ${CONTAINER_NAME} is not running. Start it first, then run this script again." >&2
        exit 1
    fi

    exec docker exec -it "${DOCKER_ENV_ARGS[@]}" "${CONTAINER_NAME}" bash -lc \
        "cd ${CONTAINER_WORKSPACE} && exec ${CONTAINER_WORKSPACE}/quick_start/play_rosbag.sh --inside-container $(quote_args "$@")"
fi

source "${CONTAINER_WORKSPACE}/environment.sh" 150
set -u

BAG_DIR="${BAG_DIR:-${CONTAINER_WORKSPACE}/rosbags}"
USE_REMAP="${USE_REMAP:-0}"
LIST_ONLY=0
ROS2_ARGS=()
BAG_INPUT=""

# Set USE_REMAP=1 to enable these ros2 topic remaps during bag playback.
# Add one "from:=to" line for each topic you want to remap.
REMAP_RULES=(
    "/locobot/camera/camera/color/image_raw/compressed:=/camera_top/camera_top/color/image_raw/compressed"
    "/locobot/camera/camera/color/camera_info:=/camera_top/camera_top/color/camera_info"
    "/locobot/commands/velocity:=/locobot/commands/velocity"
    "/locobot/odom:=/locobot/odom"
    "/locobot/tf_static_relay:=/locobot/tf_static_relay"
)

list_bags() {
    if [[ ! -d "$BAG_DIR" ]]; then
        echo "Rosbag directory not found: ${BAG_DIR}" >&2
        return 1
    fi

    find "$BAG_DIR" -mindepth 1 -maxdepth 1 -type d | sort
}

latest_bag() {
    list_bags | while read -r candidate; do
        if [[ -f "${candidate}/metadata.yaml" ]]; then
            printf '%s\n' "$candidate"
        fi
    done | tail -n 1
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        -h|--help)
            usage
            exit 0
            ;;
        -l|--list)
            LIST_ONLY=1
            shift
            ;;
        --)
            shift
            ROS2_ARGS+=("$@")
            break
            ;;
        -*)
            echo "Unknown option: $1" >&2
            usage
            exit 2
            ;;
        *)
            if [[ -n "$BAG_INPUT" ]]; then
                echo "Only one bag name/path can be provided." >&2
                usage
                exit 2
            fi
            BAG_INPUT="$1"
            shift
            ;;
    esac
done

if [[ "$LIST_ONLY" -eq 1 ]]; then
    echo "Available rosbags in ${BAG_DIR}:"
    list_bags
    exit 0
fi

if [[ ! -d "$BAG_DIR" ]]; then
    echo "Rosbag directory not found: ${BAG_DIR}" >&2
    exit 1
fi

if [[ -z "$BAG_INPUT" ]]; then
    BAG_INPUT="$DEFAULT_BAG_NAME"
    if [[ -z "$BAG_INPUT" ]]; then
        BAG_INPUT="$(latest_bag)"
    fi

    if [[ -z "$BAG_INPUT" ]]; then
        echo "No rosbag with metadata.yaml found in ${BAG_DIR}" >&2
        exit 1
    fi
fi

case "$BAG_INPUT" in
    "${HOST_WORKSPACE}/rosbags"*)
        BAG_INPUT="${CONTAINER_WORKSPACE}/rosbags${BAG_INPUT#"${HOST_WORKSPACE}/rosbags"}"
        ;;
    /*)
        ;;
    *)
        BAG_INPUT="${BAG_DIR}/${BAG_INPUT}"
        ;;
esac

if [[ ! -d "$BAG_INPUT" ]]; then
    echo "Rosbag not found: ${BAG_INPUT}" >&2
    echo "Use '$0 --list' to see available bags." >&2
    exit 1
fi

if [[ ! -f "${BAG_INPUT}/metadata.yaml" ]]; then
    echo "metadata.yaml not found in: ${BAG_INPUT}" >&2
    echo "Please pass the rosbag directory created by 'ros2 bag record'." >&2
    exit 1
fi

echo "Playing rosbag: ${BAG_INPUT}"
if [[ "$USE_REMAP" == "1" ]]; then
    REMAP_ARGS=(--ros-args)
    for rule in "${REMAP_RULES[@]}"; do
        REMAP_ARGS+=("-r" "$rule")
    done

    echo "Topic remap: enabled"
    printf '  %s\n' "${REMAP_RULES[@]}"
    ros2 bag play "$BAG_INPUT" "${ROS2_ARGS[@]}" "${REMAP_ARGS[@]}"
else
    echo "Topic remap: disabled"
    ros2 bag play "$BAG_INPUT" "${ROS2_ARGS[@]}"
fi
