from launch import LaunchDescription
from launch_ros.actions import Node

def generate_launch_description():
    """啟動 ROS2 版本的 rosbridge_server 與 rosapi_node，對應原 Terminal 5 的功能"""
    
    rosbridge_websocket_node = Node(
        package='rosbridge_server',
        executable='rosbridge_websocket',
        name='rosbridge_websocket',
        output='screen',
        parameters=[
            {'port': 9090},
            # 視需求可以加入 websocket 其他設定如 address 等
        ]
    )

    # 通常搭配 rosapi 一起啟動，讓前端能取得 topic 清單
    rosapi_node = Node(
        package='rosapi',
        executable='rosapi_node',
        name='rosapi',
        output='screen'
    )

    return LaunchDescription([
        rosbridge_websocket_node,
        rosapi_node
    ])
