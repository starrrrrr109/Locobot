#!/usr/bin/env python3
"""Keyboard teleop for Locobot base via /locobot/commands/velocity."""

import sys
import termios
import tty
from select import select

import rclpy
from rclpy.executors import ExternalShutdownException, SingleThreadedExecutor
from rclpy.node import Node
from geometry_msgs.msg import Twist


KEY_UP = "UP"
KEY_DOWN = "DOWN"
KEY_LEFT = "LEFT"
KEY_RIGHT = "RIGHT"
KEY_STOP = "STOP"
KEY_QUIT = "QUIT"


class KeyboardTeleop(Node):
    def __init__(self):
        super().__init__("keyboard_teleop")

        if not sys.stdin.isatty():
            raise RuntimeError("stdin is not a TTY; run this in a terminal.")

        self.linear_speed = float(self.declare_parameter("linear_speed", 0.2).value)
        self.angular_speed = float(self.declare_parameter("angular_speed", 1.0).value)
        self.repeat_rate = float(self.declare_parameter("repeat_rate", 30.0).value)
        self.stop_timeout = float(self.declare_parameter("stop_timeout", 0.6).value)

        self.publisher = self.create_publisher(Twist, "/locobot/commands/velocity", 10)
        self.current_twist = Twist()
        self.last_key_time = self.get_clock().now()
        self._quit = False

        self._terminal_settings = termios.tcgetattr(sys.stdin)
        tty.setraw(sys.stdin.fileno())

        self.timer = self.create_timer(1.0 / self.repeat_rate, self._on_timer)

        self.get_logger().info("Keyboard teleop started.")
        self.get_logger().info("Use arrow keys to move, space to stop, q to quit.")

    def _read_key(self):
        if select([sys.stdin], [], [], 0)[0]:
            char = sys.stdin.read(1)
            if char == "\x03":
                return KEY_QUIT
            if char == "\x1a":
                return KEY_QUIT
            if char == " ":
                return KEY_STOP
            if char in ("q", "Q"):
                return KEY_QUIT
            if char == "\x1b":
                seq = sys.stdin.read(2)
                if seq == "[A":
                    return KEY_UP
                if seq == "[B":
                    return KEY_DOWN
                if seq == "[C":
                    return KEY_RIGHT
                if seq == "[D":
                    return KEY_LEFT
        return None

    def _apply_key(self, key):
        if key == KEY_UP:
            self.current_twist.linear.x = self.linear_speed
            self.current_twist.angular.z = 0.0
        elif key == KEY_DOWN:
            self.current_twist.linear.x = -self.linear_speed
            self.current_twist.angular.z = 0.0
        elif key == KEY_LEFT:
            self.current_twist.linear.x = 0.0
            self.current_twist.angular.z = self.angular_speed
        elif key == KEY_RIGHT:
            self.current_twist.linear.x = 0.0
            self.current_twist.angular.z = -self.angular_speed
        elif key == KEY_STOP:
            self.current_twist = Twist()

    def _on_timer(self):
        key = self._read_key()
        now = self.get_clock().now()

        if key == KEY_QUIT:
            self.current_twist = Twist()
            self.publisher.publish(self.current_twist)
            self._quit = True
            return
        if key:
            self._apply_key(key)
            self.last_key_time = now
        elif self.stop_timeout <= 0.0:
            self.current_twist = Twist()

        if self.stop_timeout > 0.0 and (now - self.last_key_time).nanoseconds > int(self.stop_timeout * 1e9):
            self.current_twist = Twist()

        self.publisher.publish(self.current_twist)

    def shutdown(self):
        self.publisher.publish(Twist())
        if self._terminal_settings is not None:
            termios.tcsetattr(sys.stdin, termios.TCSANOW, self._terminal_settings)
            self._terminal_settings = None

    @property
    def should_quit(self):
        return self._quit


def main(args=None):
    rclpy.init(args=args)
    node = None
    executor = SingleThreadedExecutor()
    try:
        node = KeyboardTeleop()
        executor.add_node(node)
        while rclpy.ok() and not node.should_quit:
            executor.spin_once(timeout_sec=0.02)
    except (KeyboardInterrupt, ExternalShutdownException):
        pass
    finally:
        if node is not None:
            node.shutdown()
            executor.remove_node(node)
            node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == "__main__":
    main()
