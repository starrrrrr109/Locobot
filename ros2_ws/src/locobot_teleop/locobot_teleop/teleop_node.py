#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import rclpy
import time
from rclpy.node import Node
from geometry_msgs.msg import Twist
import sys, select, termios, tty

msg = """
Locobot 鍵盤控制節點已啟動 (ROS 2)!
---------------------------
移動方式 (支援 WASD 與 方向鍵)：
   w 或 ↑ : 前進
   s 或 ↓ : 後退
   a 或 ← : 左轉
   d 或 → : 右轉

空白鍵 (Space) : 停止
CTRL-C : 退出程式
"""

key_bindings = {
    'w': (1.0, 0.0),
    's': (-1.0, 0.0),
    'a': (0.0, 1.0),
    'd': (0.0, -1.0),
    '\x1b[A': (1.0, 0.0),
    '\x1b[B': (-1.0, 0.0),
    '\x1b[C': (0.0, -1.0),
    '\x1b[D': (0.0, 1.0),
    ' ': (0.0, 0.0),
}

def getKey(settings, timeout=0.05):
    """取得按鍵，若超過 timeout 時間沒有輸入，則回傳空字串"""
    tty.setraw(sys.stdin.fileno())
    # 使用 select 等待 stdin，設定超時時間為 0.1 秒
    rlist, _, _ = select.select([sys.stdin], [], [], timeout)

    if rlist:
        key = sys.stdin.read(1)
        # 防止單按 ESC 鍵導致卡死，確保方向鍵能正確被捕捉
        if key == '\x1b':
            rlist2, _, _ = select.select([sys.stdin], [], [], 0.05)
            if rlist2:
                key += sys.stdin.read(2)
    else:
        key = ''  # 超時沒有按鍵
        
    termios.tcsetattr(sys.stdin, termios.TCSADRAIN, settings)
    return key

def main(args=None):
    rclpy.init(args=args)
    node = rclpy.create_node('locobot_teleop_keyboard')

    # 建立 Publisher，確保 Topic 名稱正確
    pub = node.create_publisher(Twist, '/locobot/commands/velocity', 10)

    speed = 0.2
    turn = 0.5
    x = 0.0
    th = 0.0

    # 記錄最後一次按下按鍵的時間
    last_key_time = time.time()

    settings = termios.tcgetattr(sys.stdin)
    print(msg)

    try:
        while rclpy.ok():
            key = getKey(settings, timeout=0.05)
            
            if key in key_bindings:
                x = key_bindings[key][0]
                th = key_bindings[key][1]
                last_key_time = time.time()  # 更新按鍵時間
                
            elif key == '':
                # 解決鍵盤連發的系統延遲：超過 0.4 秒沒收到按鍵，才判定為放開
                if (time.time() - last_key_time) > 0.4:
                    x = 0.0
                    th = 0.0
                    
            else:
                # 捕捉 CTRL-C 結束訊號
                if key == '\x03':
                    break

            twist = Twist()
            twist.linear.x = x * speed
            twist.linear.y = 0.0
            twist.linear.z = 0.0
            twist.angular.x = 0.0
            twist.angular.y = 0.0
            twist.angular.z = th * turn
            
            pub.publish(twist)

    except Exception as e:
        print(e)

    finally:
        # 關閉時強制停止
        twist = Twist()
        twist.linear.x = 0.0
        twist.angular.z = 0.0
        pub.publish(twist)
        
        termios.tcsetattr(sys.stdin, termios.TCSADRAIN, settings)
        node.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()
