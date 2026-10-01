from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution
from launch_ros.substitutions import FindPackageShare


def _camera_include(camera_id: int):
    serial = LaunchConfiguration(f'serial_no_{camera_id}')
    namespace = LaunchConfiguration(f'camera_namespace_{camera_id}')
    name = LaunchConfiguration(f'camera_name_{camera_id}')
    inter_cam_sync_mode = LaunchConfiguration(f'inter_cam_sync_mode_{camera_id}')

    realsense_launch_dir = PathJoinSubstitution([
        FindPackageShare('realsense2_camera'),
        'launch',
    ])

    return IncludeLaunchDescription(
        PythonLaunchDescriptionSource([realsense_launch_dir, '/rs_launch.py']),
        launch_arguments={
            'serial_no': serial,
            'camera_namespace': namespace,
            'camera_name': name,
            'enable_color': 'true',
            'enable_depth': 'true',
            'align_depth.enable': 'true',
            'enable_sync': 'true',
            'rgb_camera.color_profile': '640x480x30',
            'depth_module.depth_profile': '640x480x30',
            'depth_module.inter_cam_sync_mode': inter_cam_sync_mode,
        }.items(),
    )


def generate_launch_description():
    declared_args = [
        DeclareLaunchArgument('serial_no_1', default_value='', description='Serial number for camera 1'),
        DeclareLaunchArgument('serial_no_2', default_value='', description='Serial number for camera 2'),
        DeclareLaunchArgument('serial_no_3', default_value='', description='Serial number for camera 3'),
        DeclareLaunchArgument('camera_namespace_1', default_value='camera_1', description='Namespace for camera 1'),
        DeclareLaunchArgument('camera_namespace_2', default_value='camera_2', description='Namespace for camera 2'),
        DeclareLaunchArgument('camera_namespace_3', default_value='camera_3', description='Namespace for camera 3'),
        DeclareLaunchArgument('camera_name_1', default_value='camera', description='Node name for camera 1'),
        DeclareLaunchArgument('camera_name_2', default_value='camera', description='Node name for camera 2'),
        DeclareLaunchArgument('camera_name_3', default_value='camera', description='Node name for camera 3'),
        DeclareLaunchArgument(
            'inter_cam_sync_mode_1',
            default_value='0',
            description='Inter-camera sync mode for camera 1 (0=default, 1=master, 2=slave)',
        ),
        DeclareLaunchArgument(
            'inter_cam_sync_mode_2',
            default_value='0',
            description='Inter-camera sync mode for camera 2 (0=default, 1=master, 2=slave)',
        ),
        DeclareLaunchArgument(
            'inter_cam_sync_mode_3',
            default_value='0',
            description='Inter-camera sync mode for camera 3 (0=default, 1=master, 2=slave)',
        ),
    ]

    return LaunchDescription(
        declared_args
        + [
            _camera_include(1),
            _camera_include(2),
            _camera_include(3),
        ]
    )
