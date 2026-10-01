from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    input_topic = LaunchConfiguration("input_topic")
    output_topic = LaunchConfiguration("output_topic")
    rate = LaunchConfiguration("rate")

    return LaunchDescription(
        [
            DeclareLaunchArgument("input_topic", default_value="/tf_static"),
            DeclareLaunchArgument("output_topic", default_value="/locobot/static_tf_relay"),
            DeclareLaunchArgument("rate", default_value="2.0"),
            Node(
                package="wfh_locobot_control",
                executable="filtered_static_tf_relay",
                name="locobot_static_tf_relay",
                output="screen",
                arguments=[
                    "--input-topic",
                    input_topic,
                    "--output-topic",
                    output_topic,
                    "--rate",
                    rate,
                ],
            ),
        ]
    )
