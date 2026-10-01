from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription
from launch.conditions import IfCondition
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution
from launch_ros.actions import Node
from launch_ros.substitutions import FindPackageShare


def generate_launch_description():
    serial_no = LaunchConfiguration('serial_no')
    camera_namespace = LaunchConfiguration('camera_namespace')
    camera_name = LaunchConfiguration('camera_name')
    base_frame = LaunchConfiguration('base_frame')
    camera_frame = LaunchConfiguration('camera_frame')
    publish_static_tf = LaunchConfiguration('publish_static_tf')

    x = LaunchConfiguration('x')
    y = LaunchConfiguration('y')
    z = LaunchConfiguration('z')
    roll = LaunchConfiguration('roll')
    pitch = LaunchConfiguration('pitch')
    yaw = LaunchConfiguration('yaw')

    realsense_launch_dir = PathJoinSubstitution([
        FindPackageShare('realsense2_camera'),
        'launch',
    ])

    camera_launch = IncludeLaunchDescription(
        PythonLaunchDescriptionSource([realsense_launch_dir, '/rs_launch.py']),
        launch_arguments={
            'serial_no': serial_no,
            'camera_namespace': camera_namespace,
            'camera_name': camera_name,
            'enable_color': 'true',
            'enable_depth': 'true',
            'align_depth.enable': 'true',
            'enable_sync': 'true',
            'rgb_camera.color_profile': '640x480x30',
            'depth_module.depth_profile': '640x480x30',
            # Keep RealSense base frame consistent with the TF child frame below.
            'base_frame_id': camera_frame,
        }.items(),
    )

    static_tf = Node(
        package='tf2_ros',
        executable='static_transform_publisher',
        name='base_to_camera_static_tf',
        condition=IfCondition(publish_static_tf),
        arguments=[
            '--x',
            x,
            '--y',
            y,
            '--z',
            z,
            '--roll',
            roll,
            '--pitch',
            pitch,
            '--yaw',
            yaw,
            '--frame-id',
            base_frame,
            '--child-frame-id',
            camera_frame,
        ],
    )

    declared_args = [
        DeclareLaunchArgument('serial_no', default_value='', description='RealSense serial number'),
        DeclareLaunchArgument('camera_namespace', default_value='camera_1', description='Camera ROS namespace'),
        DeclareLaunchArgument('camera_name', default_value='camera', description='RealSense node name'),
        DeclareLaunchArgument('base_frame', default_value='base_link', description='Parent TF frame'),
        DeclareLaunchArgument('camera_frame', default_value='camera_1_link', description='Camera TF child frame'),
        DeclareLaunchArgument('publish_static_tf', default_value='true', description='Publish base_frame -> camera_frame static TF'),
        DeclareLaunchArgument('x', default_value='0.0', description='base_frame -> camera_frame translation X (m)'),
        DeclareLaunchArgument('y', default_value='0.0', description='base_frame -> camera_frame translation Y (m)'),
        DeclareLaunchArgument('z', default_value='0.0', description='base_frame -> camera_frame translation Z (m)'),
        DeclareLaunchArgument('roll', default_value='0.0', description='base_frame -> camera_frame roll (rad)'),
        DeclareLaunchArgument('pitch', default_value='0.0', description='base_frame -> camera_frame pitch (rad)'),
        DeclareLaunchArgument('yaw', default_value='0.0', description='base_frame -> camera_frame yaw (rad)'),
    ]

    return LaunchDescription(declared_args + [camera_launch, static_tf])