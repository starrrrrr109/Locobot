from launch import LaunchDescription
from launch.actions import IncludeLaunchDescription, DeclareLaunchArgument
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import PathJoinSubstitution, LaunchConfiguration
from launch_ros.substitutions import FindPackageShare

def generate_launch_description():
    """啟動 ROS2 版本的 Intel RealSense D435 節點，對應原 Terminal 4 的功能"""
    
    # 宣告可從外部帶入的參數
    serial_no = LaunchConfiguration('serial_no', default='')
    camera_name = LaunchConfiguration('camera_name', default='camera_locobot')

    serial_no_arg = DeclareLaunchArgument(
        'serial_no',
        default_value='',
        description='Hardware serial number to connect to a specific RealSense device'
    )

    camera_name_arg = DeclareLaunchArgument(
        'camera_name',
        default_value='camera_locobot',
        description='Namespace for the camera topics (e.g., camera_top, camera_wrist)'
    )

    # 尋找 realsense2_camera 包的預設啟動檔
    realsense_launch_dir = PathJoinSubstitution([
        FindPackageShare('realsense2_camera'),
        'launch'
    ])

    return LaunchDescription([
        serial_no_arg,
        camera_name_arg,
        IncludeLaunchDescription(
            PythonLaunchDescriptionSource([realsense_launch_dir, '/rs_launch.py']),
            launch_arguments={
                'serial_no': serial_no,
                'camera_name': camera_name,  # 這決定了相機的 Topic Prefix / Namespace
                'enable_color': 'true',
                'enable_depth': 'true',
                'align_depth.enable': 'true',
                'enable_sync': 'true',
                'rgb_camera.color_profile': '640x480x30',
                'depth_module.depth_profile': '640x480x30'
            }.items()
        )
    ])
