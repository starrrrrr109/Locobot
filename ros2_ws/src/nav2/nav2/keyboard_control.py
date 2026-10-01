#!/usr/bin/env python3
import sys
import select
import termios
import tty
import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Twist

HELP_MSG = """
==================================================
 🤖 LoCoBot 純底盤鍵盤控制
==================================================
 🚗 【底盤移動】
        w : 前進          s : 後退
        a : 原地左轉      d : 原地右轉
        q : 左前彎道      e : 右前彎道
        z : 左後彎道      c : 右後彎道

 ⚡ 【速度切換】
        1 : 標準模式 (線速度 0.20 m/s, 角速度 0.80 rad/s)
        2 : 高速模式 (線速度 0.45 m/s, 角速度 1.20 rad/s)

 🛑 【煞車與離開】
        空白鍵 (Space) / k : 緊急煞車
        按放開鍵自動停止，按 CTRL-C 退出程式
==================================================
"""

# 按鍵移動方向映射 (linear_x, angular_z)
MOVE_BINDINGS = {
    'w': (1.0, 0.0),
    's': (-1.0, 0.0),
    'a': (0.0, 1.0),
    'd': (0.0, -1.0),
    'q': (1.0, 1.0),
    'e': (1.0, -1.0),
    'z': (-1.0, -1.0),
    'c': (-1.0, 1.0),
}

# 鍵盤非阻塞讀取
def get_key(settings, timeout=0.05):
    tty.setraw(sys.stdin.fileno())
    rlist, _, _ = select.select([sys.stdin], [], [], timeout)
    if rlist:
        key = sys.stdin.read(1)
    else:
        key = ''
    termios.tcsetattr(sys.stdin, termios.TCSADRAIN, settings)
    return key


class LocobotBaseTeleop(Node):
    def __init__(self):
        super().__init__('locobot_base_keyboard_teleop')

        # 發布底盤速度指令
        self.vel_pub = self.create_publisher(
            Twist, '/locobot/commands/velocity', 10)

        # 預設速度參數
        self.scale_linear = 0.20
        self.scale_angular = 0.80

        self.get_logger().info('LoCoBot 純底盤鍵盤控制節點已啟動！')


def main(args=None):
    settings = termios.tcgetattr(sys.stdin)
    rclpy.init(args=args)
    node = LocobotBaseTeleop()

    print(HELP_MSG)

    x = 0.0
    th = 0.0

    try:
        while rclpy.ok():
            key = get_key(settings, timeout=0.05)

            if key in MOVE_BINDINGS:
                x = MOVE_BINDINGS[key][0]
                th = MOVE_BINDINGS[key][1]
            elif key in [' ', 'k']:
                x = 0.0
                th = 0.0
            elif key == '1':
                node.scale_linear = 0.20
                node.scale_angular = 0.80
                print(f"➜ 切換至【標準模式】: 線速度={node.scale_linear} m/s, 角速度={node.scale_angular} rad/s")
                continue
            elif key == '2':
                node.scale_linear = 0.45
                node.scale_angular = 1.20
                print(f"🚀 切換至【高速模式】: 線速度={node.scale_linear} m/s, 角速度={node.scale_angular} rad/s")
                continue
            elif key == '\x03':  # Ctrl + C
                break
            else:
                # 沒按按鍵時自動減速停止
                x = 0.0
                th = 0.0

            # 發布速度訊息
            twist = Twist()
            twist.linear.x = x * node.scale_linear
            twist.angular.z = th * node.scale_angular
            node.vel_pub.publish(twist)

    except Exception as e:
        print(f"程式異常: {e}")

    finally:
        # 結束時發送停止指令
        stop_twist = Twist()
        node.vel_pub.publish(stop_twist)
        node.destroy_node()
        rclpy.shutdown()
        termios.tcsetattr(sys.stdin, termios.TCSADRAIN, settings)


if __name__ == '__main__':
    main()