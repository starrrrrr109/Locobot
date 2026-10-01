#!/bin/bash

# Load ROS environment (required inside the container)
source /workspace/environment.sh 150

set -euo pipefail

if [[ "${BASH_SOURCE[0]}" != "$0" ]]; then
	echo "Please run this script, do not source it: ./keyboard_control.sh"
	return 1
fi

LINEAR_SPEED=${LINEAR_SPEED:-0.25}
ANGULAR_SPEED=${ANGULAR_SPEED:-0.65}
REPEAT_RATE=${REPEAT_RATE:-30.0}
STOP_TIMEOUT=${STOP_TIMEOUT:-0.6}
ORIGINAL_STTY=""

usage() {
	echo "Usage: $0 [-l linear_speed] [-a angular_speed] [-r repeat_rate] [-t stop_timeout] [-- <ros2 args>]"
	echo "Env vars: LINEAR_SPEED, ANGULAR_SPEED, REPEAT_RATE, STOP_TIMEOUT"
}

while getopts ":l:a:r:t:h" opt; do
	case "$opt" in
		l) LINEAR_SPEED="$OPTARG" ;;
		a) ANGULAR_SPEED="$OPTARG" ;;
		r) REPEAT_RATE="$OPTARG" ;;
		t) STOP_TIMEOUT="$OPTARG" ;;
		h) usage; exit 0 ;;
		\?) echo "Unknown option: -$OPTARG"; usage; exit 2 ;;
		:) echo "Option -$OPTARG requires an argument"; usage; exit 2 ;;
	esac
done
shift $((OPTIND - 1))

cleanup() {
	if [[ -n "$ORIGINAL_STTY" ]] && [[ -t 0 ]]; then
		stty "$ORIGINAL_STTY" 2>/dev/null || true
	fi
}

if [[ -t 0 ]]; then
	ORIGINAL_STTY=$(stty -g)
fi

trap 'cleanup EXIT' EXIT

ros2 run wfh_locobot_control keyboard_teleop \
	--ros-args \
	-p linear_speed:="$LINEAR_SPEED" \
	-p angular_speed:="$ANGULAR_SPEED" \
	-p repeat_rate:="$REPEAT_RATE" \
	-p stop_timeout:="$STOP_TIMEOUT" \
	"$@"
