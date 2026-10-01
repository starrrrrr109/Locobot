#!/bin/bash

source ~/WFH_locobot/environment.sh
source ~/WFH_locobot/set_ip.sh $1 $2
rosrun hand_eye_calibration static_hand_eye_calibration_left 
rosrun hand_eye_calibration get_transform ~/WFH_locobot/ROS/catkin_ws/src/hand_eye_calibration/data/calibration.txt
rm ~/WFH_locobot/ROS/catkin_ws/src/hand_eye_calibration/data/calibration.txt
rosservice call /calibration

