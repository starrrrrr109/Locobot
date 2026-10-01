#!/bin/bash

source ~/WFH_locobot/environment.sh
source ~/WFH_locobot/set_ip.sh $1 $2
roslaunch apriltag_ros april_tag_bundle.launch 


