from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    return LaunchDescription([
        DeclareLaunchArgument(
            "image_topic",
            default_value="/locobot/camera/camera/color/image_raw/compressed",
        ),
        DeclareLaunchArgument(
            "output_topic",
            default_value="/locobot/camera_pose_odom",
        ),
        DeclareLaunchArgument("target_frame", default_value="locobot/odom"),
        DeclareLaunchArgument("lookup_timeout_sec", default_value="0.05"),
        Node(
            package="wfh_locobot_control",
            executable="camera_pose_odom_relay",
            name="camera_pose_odom_relay",
            output="screen",
            parameters=[{
                "image_topic": LaunchConfiguration("image_topic"),
                "output_topic": LaunchConfiguration("output_topic"),
                "target_frame": LaunchConfiguration("target_frame"),
                "lookup_timeout_sec": LaunchConfiguration("lookup_timeout_sec"),
            }],
        ),
    ])
