#!/usr/bin/env python3
import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Joy, JointState
from geometry_msgs.msg import Twist
# 引入 Interbotix 專用的群組控制與單軸控制訊息
from interbotix_xs_msgs.msg import JointGroupCommand, JointSingleCommand 

class LocobotFullTeleopNode(Node):
    def __init__(self):
        super().__init__('locobot_full_teleop_node')
        
        # 1. 訂閱搖桿訊號 /joy
        self.joy_sub = self.create_subscription(
            Joy, '/joy', self.joy_callback, 10)
        
        # 2. 【修正點】訂閱純手臂狀態，避開底盤雜訊，確保精準初始化
        self.joint_sub = self.create_subscription(
            JointState, '/locobot/dynamixel/joint_states', self.joint_states_callback, 10)
        
        # 3. 發布底盤速度指令
        self.vel_pub = self.create_publisher(
            Twist, '/locobot/commands/velocity', 10)
        
        # 4. 發布手臂群組角度指令 (控制 waist, shoulder, elbow 等)
        self.arm_pub = self.create_publisher(
            JointGroupCommand, '/locobot/commands/joint_group', 10)
            
        # 5. 發布夾爪單軸指令
        self.gripper_pub = self.create_publisher(
            JointSingleCommand, '/locobot/commands/joint_single', 10)
        
        # 🎮 Logitech F710 搖桿映射配置 (X 模式)
        self.AXIS_BASE_LINEAR = 1     # 左搖桿 上下 (底盤前後)
        self.AXIS_BASE_ANGULAR = 0    # 左搖桿 左右 (底盤旋轉)
        self.AXIS_ARM_WAIST = 3       # 右搖桿 左右 (第一軸：腰部)
        self.AXIS_ARM_SHOULDER = 4    # 右搖桿 上下 (第二軸：肩膀)
        self.AXIS_ARM_ELBOW = 7       # 十字鍵 上下 (第三軸：手肘)
        
        self.BTN_DEADMAN = 4          # LB 鍵 (安全死人開關)
        self.BTN_GRIPPER_CLOSE = 0    # A 鍵 (夾爪閉合)
        self.BTN_GRIPPER_OPEN = 1     # B 鍵 (夾爪張開)
        
        # ⚙️ 控制參數設定
        self.MAX_LINEAR_SPEED = 0.2
        self.MAX_ANGULAR_SPEED = 1.0
        self.ARM_SPEED_SCALE = 0.01    # 調小增量，防止瞬間加速過載卡死
        
        # 🦾 手臂與夾爪控制快取
        self.joint_names = ['waist', 'shoulder', 'elbow', 'wrist_angle', 'wrist_rotate']
        self.target_joints = [0.0, 0.0, 0.0, 0.0, 0.0]
        
        # 🧲 夾爪極限參數 (Interbotix 官方標準單位：公尺)
        self.GRIPPER_MIN = 0.015       # 完全閉合
        self.GRIPPER_MAX = 0.037       # 完全張開
        self.target_gripper = 0.02
        
        self.joints_initialized = False
        
        self.get_logger().info('Locobot 全功能控制節點已啟動！')
        self.get_logger().info('⏳ 正在透過 /locobot/dynamixel/joint_states 鎖定手臂初始姿態...')

    def joint_states_callback(self, msg: JointState):
        # 唯獨在第一次啟動時，抓取實體馬達數據作為控制起點
        if not self.joints_initialized:
            pos_map = {name: pos for name, pos in zip(msg.name, msg.position)}
            try:
                self.target_joints = [
                    pos_map['waist'],
                    pos_map['shoulder'],
                    pos_map['elbow'],
                    pos_map['wrist_angle'],
                    pos_map['wrist_rotate']
                ]
                # 嘗試抓取夾爪目前的開合狀態 (通常對應 left_finger)
                self.target_gripper = pos_map.get('left_finger', 0.02)
                
                self.joints_initialized = True
                self.get_logger().info('✅ 手臂姿態同步成功！控制解鎖。')
                self.get_logger().info('👉 操作說明：按住 LB 鍵 ＋')
                self.get_logger().info('   - 左搖桿：控制底盤移動')
                self.get_logger().info('   - 右搖桿：控制腰部與肩膀')
                self.get_logger().info('   - 十字鍵上下：控制手肘升降 🆙')
                self.get_logger().info('   - A 鍵 / B 鍵：控制夾爪閉合與張開 🧲')
            except KeyError:
                pass

    def joy_callback(self, msg: Joy):
        if not self.joints_initialized:
            return

        twist = Twist()
        
        # 檢查安全開關 (LB 鍵) 是否被按下
        if msg.buttons[self.BTN_DEADMAN] == 1:
            
            # === 🚗 【底盤控制】 ===
            twist.linear.x = msg.axes[self.AXIS_BASE_LINEAR] * self.MAX_LINEAR_SPEED
            twist.angular.z = msg.axes[self.AXIS_BASE_ANGULAR] * self.MAX_ANGULAR_SPEED
            
            # === 🦾 【手臂關節控制】 ===
            arm_moved = False
            
            # 右搖桿 左右 -> 腰部 (Waist)
            if abs(msg.axes[self.AXIS_ARM_WAIST]) > 0.1:
                self.target_joints[0] += msg.axes[self.AXIS_ARM_WAIST] * self.ARM_SPEED_SCALE
                arm_moved = True
                
            # 右搖桿 上下 -> 肩膀 (Shoulder)
            if abs(msg.axes[self.AXIS_ARM_SHOULDER]) > 0.1:
                self.target_joints[1] += msg.axes[self.AXIS_ARM_SHOULDER] * self.ARM_SPEED_SCALE
                arm_moved = True
            
            # 十字鍵 上下 -> 手肘 (Elbow)
            if abs(msg.axes[self.AXIS_ARM_ELBOW]) > 0.1:
                self.target_joints[2] += msg.axes[self.AXIS_ARM_ELBOW] * self.ARM_SPEED_SCALE
                arm_moved = True
            
            # 如果手臂位置有變動，發布群組指令
            if arm_moved:
                arm_cmd = JointGroupCommand()
                arm_cmd.name = 'arm'
                arm_cmd.cmd = self.target_joints
                self.arm_pub.publish(arm_cmd)
                
            # === 🧲 【夾爪單軸控制】 ===
            gripper_changed = False
            
            if msg.buttons[self.BTN_GRIPPER_CLOSE] == 1:    # 按下 A 鍵
                self.target_gripper -= 0.002                # 每次減少間距 (閉合)
                gripper_changed = True
            elif msg.buttons[self.BTN_GRIPPER_OPEN] == 1:   # 按下 B 鍵
                self.target_gripper += 0.002                # 每次放大間距 (張開)
                gripper_changed = True
                
            if gripper_changed:
                # 限制夾爪在硬體安全邊界內
                self.target_gripper = max(self.GRIPPER_MIN, min(self.GRIPPER_MAX, self.target_gripper))
                
                gripper_cmd = JointSingleCommand()
                gripper_cmd.name = 'gripper'
                gripper_cmd.cmd = self.target_gripper
                self.gripper_pub.publish(gripper_cmd)
            
        else:
            # 未按住安全開關，底盤速度安全歸零
            twist.linear.x = 0.0
            twist.angular.z = 0.0
            
        self.vel_pub.publish(twist)

def main(args=None):
    rclpy.init(args=args)
    node = LocobotFullTeleopNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        stop_twist = Twist()
        node.vel_pub.publish(stop_twist)
        node.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()