from setuptools import find_packages, setup

package_name = "wfh_locobot_control"

setup(
    name=package_name,
    version="0.0.0",
    packages=find_packages(exclude=["test"]),
    data_files=[
        ("share/ament_index/resource_index/packages", ["resource/" + package_name]),
        ("share/" + package_name, ["package.xml"]),
        ("share/" + package_name + "/launch", [
            "launch/locobot_main.launch.py",
            "launch/triple_camera.launch.py",
            "launch/single_camera_with_tf.launch.py",
            "launch/rosbridge.launch.py",
            "launch/camera.launch.py",
            "launch/locobot_static_tf_relay.launch.py",
            "launch/camera_pose_odom_relay.launch.py",
        ]),
    ],
    install_requires=["setuptools"],
    zip_safe=True,
    maintainer="locobot",
    maintainer_email="locobot@todo.todo",
    description="Locobot ROS2 Humble Control Wrapper",
    license="TODO: License declaration",
    entry_points={
        "console_scripts": [
            "tf_relay_node = wfh_locobot_control.tf_relay_node:main",
            "tf_relay_node.py = wfh_locobot_control.tf_relay_node:main",
            "filtered_static_tf_relay = wfh_locobot_control.filtered_static_tf_relay:main",
            "keyboard_teleop = wfh_locobot_control.keyboard_teleop:main",
            "gamepad_mode_manager = wfh_locobot_control.gamepad_mode_manager:main",
            "camera_pose_odom_relay = wfh_locobot_control.camera_pose_odom_relay:main",
        ],
    },
)
