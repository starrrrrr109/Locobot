import rclpy
from rclpy.node import Node
from rclpy.action import ActionClient
from action_msgs.msg import GoalStatus
from geometry_msgs.msg import PoseStamped
from nav2_msgs.action import NavigateToPose

class Nav2GoalSender(Node):
    def __init__(self):
        super().__init__('nav2_goal_sender_node')
        
        # 建立一個 Action Client 來發送目標點給 Nav2
        self._action_client = ActionClient(self, NavigateToPose, 'navigate_to_pose')
        
        self.get_logger().info('Nav2 Goal Sender Node 已啟動，準備發送目標點...')

    def send_goal(self, x, y, theta_z=0.0, theta_w=1.0):
        """發送目標點的主函數"""
        # 1. 初始化 Goal 訊息
        goal_msg = NavigateToPose.Goal()
        
        # 2. 設定坐標系與時間戳記
        goal_msg.pose.header.frame_id = 'map'
        goal_msg.pose.header.stamp = self.get_clock().now().to_msg()
        
        # 3. 設定目標的位置 (Position) 與朝向 (Orientation)
        goal_msg.pose.pose.position.x = x
        goal_msg.pose.pose.position.y = y
        goal_msg.pose.pose.orientation.z = theta_z
        goal_msg.pose.pose.orientation.w = theta_w
        
        # 4. 等待 Nav2 Action Server 啟動
        self.get_logger().info('正在等待 Nav2 Action Server...')
        self._action_client.wait_for_server()
        
        # 5. 非同步發送目標，並設定回傳與回饋的 Callback
        self.get_logger().info(f'正在發送目標點：X={x}, Y={y}')
        self._send_goal_future = self._action_client.send_goal_async(
            goal_msg, 
            feedback_callback=self.feedback_callback
        )
        self._send_goal_future.add_done_callback(self.goal_response_callback)

    def goal_response_callback(self, future):
        """確認伺服器是否接受目標"""
        goal_handle = future.result()
        if not goal_handle.accepted:
            self.get_logger().error('目標被 Nav2 拒絕！')
            return

        self.get_logger().info('目標已被 Nav2 接受，機器人開始移動...')
        self._get_result_future = goal_handle.get_result_async()
        self._get_result_future.add_done_callback(self.get_result_callback)

    def get_result_callback(self, future):
        """導航任務結束後的回傳結果"""
        status = future.result().status
        if status == GoalStatus.STATUS_SUCCEEDED:
            self.get_logger().info('恭喜！機器人已成功抵達目標點！')
        else:
            self.get_logger().warn(f'導航未成功，狀態碼: {status}')

    def feedback_callback(self, feedback_msg):
        """導航過程中的即時回饋（例如剩餘距離）"""
        feedback = feedback_msg.feedback
        self.get_logger().info(
            f'剩餘距離: {feedback.distance_remaining:.2f} 公尺 | 導航時間: {feedback.navigation_time.sec} 秒',
            throttle_duration_sec=2.0 # 每 2 秒輸出一次 log，避免洗版
        )


def main(args=None):
    rclpy.init(args=args)
    node = Nav2GoalSender()
    
    # 測試：啟動後直接發送一個目標點 (例如 X=1.5, Y=1.0)
    # 你可以根據你的地圖與機器人起點修改此坐標
    node.send_goal(x=1.5, y=1.0)
    
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()

if __name__ == '__main__':
    main()