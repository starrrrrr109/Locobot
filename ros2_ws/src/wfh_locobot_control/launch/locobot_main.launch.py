from launch import LaunchDescription
from launch.actions import IncludeLaunchDescription, DeclareLaunchArgument
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution
from launch_ros.substitutions import FindPackageShare

def generate_launch_description():
    # 參數宣告
    use_arm = LaunchConfiguration('use_arm', default='true')
    use_base = LaunchConfiguration('use_base', default='true')
    use_camera = LaunchConfiguration('use_camera', default='true') # 將轉接至 RealSense D435
    use_rviz = LaunchConfiguration('use_rviz', default='false')
    robot_model = LaunchConfiguration('robot_model', default='locobot_wx250s') # 依實際使用的機械臂型號調整

    # 包含 Interbotix 官方的 locobot control
    interbotix_launch_dir = PathJoinSubstitution([
        FindPackageShare('interbotix_xslocobot_control'),
        'launch'
    ])

    locobot_control_launch = IncludeLaunchDescription(
        PythonLaunchDescriptionSource([interbotix_launch_dir, '/xslocobot_control.launch.py']),
        launch_arguments={
            'robot_model': robot_model,
            'use_arm': use_arm,
            'use_base': use_base,
            'use_camera': use_camera,
            'use_rviz': use_rviz,
        }.items()
    )

    return LaunchDescription([
        locobot_control_launch
    ])
