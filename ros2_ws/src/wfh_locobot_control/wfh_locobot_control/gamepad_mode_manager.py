#!/usr/bin/env python3
"""Service-controlled Logitech F710 base teleop launcher."""

import os
import signal
import sqlite3
import subprocess
import time
from pathlib import Path

import rclpy
from rclpy.executors import ExternalShutdownException
from rclpy.node import Node
from sensor_msgs.msg import Joy, JoyFeedback
from std_msgs.msg import Empty
from std_srvs.srv import Trigger


class GamepadModeManager(Node):
    def __init__(self):
        super().__init__("gamepad_mode_manager")

        self.params_file = str(self.declare_parameter(
            "params_file",
            self._default_params_file(),
        ).value)
        self.cmd_vel_topic = str(self.declare_parameter(
            "cmd_vel_topic",
            "/locobot/commands/velocity",
        ).value)
        self.joy_device_id = int(self.declare_parameter("joy_device_id", 0).value)
        self.joy_device_name = str(self.declare_parameter("joy_device_name", "").value)
        self.record_script = str(self.declare_parameter(
            "record_script",
            self._default_record_script(),
        ).value)
        self.bag_dir = str(self.declare_parameter("bag_dir", "/workspace/rosbags").value)
        self.record_start_button = int(self.declare_parameter("record_start_button", 3).value)
        self.record_stop_button = int(self.declare_parameter("record_stop_button", 1).value)
        self.reset_odom_button = int(self.declare_parameter("reset_odom_button", 0).value)
        self.reset_odom_topic = str(self.declare_parameter(
            "reset_odom_topic",
            "/locobot/commands/reset_odometry",
        ).value)
        self.joy_retry_period = float(self.declare_parameter("joy_retry_period", 5.0).value)
        self.record_start_timeout = float(self.declare_parameter(
            "record_start_timeout",
            8.0,
        ).value)
        self.rumble_duration = float(self.declare_parameter("rumble_duration", 1.0).value)
        self.rumble_intensity = float(self.declare_parameter("rumble_intensity", 1.0).value)

        self.joy_process = None
        self.teleop_process = None
        self.record_process = None
        self.record_bag_path = None
        self.rumble_stop_timer = None
        self.previous_buttons = []
        self.last_joy_start_attempt = 0.0

        self.joy_sub = self.create_subscription(Joy, "/joy", self.joy_callback, 10)
        self.reset_odom_pub = self.create_publisher(Empty, self.reset_odom_topic, 10)
        self.joy_feedback_pub = self.create_publisher(JoyFeedback, "/joy/set_feedback", 10)
        self.process_timer = self.create_timer(1.0, self.check_processes)
        self.create_service(Trigger, "/switch_to_gamepad_mode", self.switch_callback)
        self.create_service(Trigger, "/stop_gamepad_mode", self.stop_callback)
        self.create_service(Trigger, "/reset_locobot_odom", self.reset_odom_callback)
        self.create_service(Trigger, "/start_rosbag_recording", self.start_recording_callback)
        self.create_service(Trigger, "/stop_rosbag_recording", self.stop_recording_callback)

        self.get_logger().info("Gamepad mode manager ready.")
        self.get_logger().info("Call /switch_to_gamepad_mode to enable Logitech F710 teleop.")
        self.get_logger().info(
            "F710 A resets odom; Y starts rosbag recording; B sends Ctrl+C to stop it."
        )

        try:
            self.ensure_joy_node()
        except OSError as exc:
            self.get_logger().warn(f"Failed to start joy_node for gamepad buttons: {exc}")

    @staticmethod
    def _default_params_file():
        candidates = (
            Path("/workspace/quick_start/teleop_twist_joy_f710.yaml"),
            Path.cwd() / "quick_start" / "teleop_twist_joy_f710.yaml",
        )
        for candidate in candidates:
            if candidate.exists():
                return str(candidate)
        return str(candidates[0])

    @staticmethod
    def _default_record_script():
        candidates = (
            Path("/workspace/quick_start/record_rosbag.sh"),
            Path.cwd() / "quick_start" / "record_rosbag.sh",
        )
        for candidate in candidates:
            if candidate.exists():
                return str(candidate)
        return str(candidates[0])

    def switch_callback(self, request, response):
        del request

        if self._is_running(self.teleop_process):
            response.success = True
            response.message = "Gamepad mode is already active."
            return response

        if not Path(self.params_file).exists():
            response.success = False
            response.message = f"teleop_twist_joy params file not found: {self.params_file}"
            return response

        self._stop_teleop_process()

        try:
            self.ensure_joy_node(force=True)
            self.teleop_process = self._start_teleop_node()
            time.sleep(0.5)
            self._raise_if_exited(self.teleop_process, "teleop_twist_joy")
        except OSError as exc:
            self._stop_teleop_process()
            response.success = False
            response.message = f"Failed to start gamepad teleop: {exc}"
            return response

        response.success = True
        response.message = (
            "Gamepad mode active. Logitech F710 left stick controls "
            f"{self.cmd_vel_topic}."
        )
        return response

    def stop_callback(self, request, response):
        del request
        self._stop_teleop_process()
        response.success = True
        response.message = "Gamepad mode stopped."
        return response

    def reset_odom_callback(self, request, response):
        del request
        self.reset_odom()
        response.success = True
        response.message = f"Published reset odometry command to {self.reset_odom_topic}."
        return response

    def start_recording_callback(self, request, response):
        del request
        success, message = self.start_recording()
        response.success = success
        response.message = message
        return response

    def stop_recording_callback(self, request, response):
        del request
        success, message = self.stop_recording()
        response.success = success
        response.message = message
        return response

    def joy_callback(self, msg):
        if self._button_pressed(msg.buttons, self.reset_odom_button):
            self.reset_odom()
        if self._button_pressed(msg.buttons, self.record_start_button):
            self.start_recording()
        if self._button_pressed(msg.buttons, self.record_stop_button):
            self.stop_recording()
        self.previous_buttons = list(msg.buttons)

    def check_processes(self):
        if self.record_process is not None and self.record_process.poll() is not None:
            self.get_logger().info(
                f"rosbag recording process exited with code {self.record_process.returncode}."
            )
            self.record_process = None
            self.record_bag_path = None

        if self.joy_process is not None and self.joy_process.poll() is not None:
            self.get_logger().warn(f"joy_node exited with code {self.joy_process.returncode}.")
            self.joy_process = None
        if self.joy_process is None:
            try:
                self.ensure_joy_node()
            except OSError:
                pass

    def ensure_joy_node(self, force=False):
        if self._is_running(self.joy_process):
            return
        now = time.monotonic()
        if not force and now - self.last_joy_start_attempt < self.joy_retry_period:
            return
        self.last_joy_start_attempt = now
        self.joy_process = self._start_joy_node()
        time.sleep(0.5)
        self._raise_if_exited(self.joy_process, "joy_node")

    def start_recording(self):
        if self._is_running(self.record_process):
            message = "rosbag recording is already running."
            self.get_logger().info(message)
            return True, message

        if not Path(self.record_script).exists():
            message = f"record script not found: {self.record_script}"
            self.get_logger().error(message)
            return False, message

        bag_dir = Path(self.bag_dir)
        bag_name = f"locobot_{time.strftime('%Y%m%d_%H%M%S')}"
        self.record_bag_path = bag_dir / bag_name

        try:
            env = os.environ.copy()
            env["BAG_DIR"] = str(bag_dir)
            env["BAG_NAME"] = bag_name
            self.record_process = self._popen(["bash", self.record_script], env=env)
        except OSError as exc:
            self.record_process = None
            self.record_bag_path = None
            message = f"Failed to start rosbag recording: {exc}"
            self.get_logger().error(message)
            return False, message

        if not self._wait_for_recording_to_start(self.record_bag_path, self.record_start_timeout):
            return_code = self.record_process.poll() if self.record_process is not None else None
            self._stop_process(self.record_process)
            self.record_process = None
            failed_path = self.record_bag_path
            self.record_bag_path = None
            message = (
                f"rosbag recording did not receive any messages within"
                f" {self.record_start_timeout:.1f}s"
                f" at {failed_path}; process exit code: {return_code}."
            )
            self.get_logger().error(message)
            return False, message

        message = f"Started rosbag recording at {self.record_bag_path}."
        self.get_logger().info(message)
        self.rumble()
        return True, message

    def stop_recording(self):
        if not self._is_running(self.record_process):
            message = "rosbag recording is not running."
            self.get_logger().info(message)
            return False, message

        try:
            os.killpg(os.getpgid(self.record_process.pid), signal.SIGINT)
        except ProcessLookupError:
            pass
        message = "Sent Ctrl+C to rosbag recording."
        self.get_logger().info(message)
        return True, message

    def reset_odom(self):
        self.reset_odom_pub.publish(Empty())
        self.get_logger().info(f"Published reset odometry command to {self.reset_odom_topic}.")

    def rumble(self):
        for _ in range(3):
            self._publish_rumble(self.rumble_intensity)
        if self.rumble_stop_timer is not None:
            self.rumble_stop_timer.cancel()
        self.rumble_stop_timer = self.create_timer(self.rumble_duration, self._stop_rumble_once)

    def _stop_rumble_once(self):
        self._publish_rumble(0.0)
        if self.rumble_stop_timer is not None:
            self.rumble_stop_timer.cancel()
            self.rumble_stop_timer = None

    def _publish_rumble(self, intensity):
        clamped_intensity = max(0.0, min(1.0, float(intensity)))
        for rumble_id in (0, 1):
            feedback = JoyFeedback()
            feedback.type = JoyFeedback.TYPE_RUMBLE
            feedback.id = rumble_id
            feedback.intensity = clamped_intensity
            self.joy_feedback_pub.publish(feedback)

    def _wait_for_recording_to_start(self, bag_path, timeout_sec):
        deadline = time.monotonic() + timeout_sec
        while time.monotonic() < deadline:
            if not self._is_running(self.record_process):
                return False
            if self._bag_has_recorded_messages(bag_path):
                return True
            time.sleep(0.1)
        return False

    @staticmethod
    def _bag_has_recorded_messages(bag_path):
        if bag_path is None or not bag_path.exists():
            return False

        for db_path in bag_path.glob("*.db3"):
            try:
                with sqlite3.connect(f"file:{db_path}?mode=ro", uri=True, timeout=0.1) as conn:
                    row = conn.execute("SELECT COUNT(*) FROM messages").fetchone()
            except sqlite3.Error:
                continue
            if row is not None and row[0] > 0:
                return True

        # This project records sqlite3 bags. If storage is changed to MCAP later,
        # keep the old "file exists" behavior rather than blocking forever.
        return any(bag_path.glob("*.mcap"))

    def _button_pressed(self, buttons, index):
        if index < 0 or index >= len(buttons):
            return False
        previous = self.previous_buttons[index] if index < len(self.previous_buttons) else 0
        return buttons[index] == 1 and previous == 0

    def _start_joy_node(self):
        command = [
            "ros2",
            "run",
            "joy",
            "joy_node",
            "--ros-args",
            "--params-file",
            self.params_file,
            "-p",
            f"device_id:={self.joy_device_id}",
        ]
        if self.joy_device_name:
            command.extend(["-p", f"device_name:={self.joy_device_name}"])
        return self._popen(command)

    def _start_teleop_node(self):
        command = [
            "ros2",
            "run",
            "teleop_twist_joy",
            "teleop_node",
            "--ros-args",
            "--params-file",
            self.params_file,
            "-r",
            f"cmd_vel:={self.cmd_vel_topic}",
        ]
        return self._popen(command)

    def _stop_teleop_process(self):
        self._stop_process(self.teleop_process)
        self.teleop_process = None

    @staticmethod
    def _popen(command, env=None):
        return subprocess.Popen(command, env=env, preexec_fn=os.setsid)

    @staticmethod
    def _is_running(process):
        return process is not None and process.poll() is None

    @staticmethod
    def _raise_if_exited(process, name):
        if process is not None and process.poll() is not None:
            raise OSError(f"{name} exited immediately with code {process.returncode}")

    def _stop_process(self, process, sig=signal.SIGINT):
        if not self._is_running(process):
            return

        try:
            os.killpg(os.getpgid(process.pid), sig)
        except ProcessLookupError:
            return

        try:
            process.wait(timeout=2.0)
        except subprocess.TimeoutExpired:
            try:
                os.killpg(os.getpgid(process.pid), signal.SIGTERM)
            except ProcessLookupError:
                pass

    def _stop_processes(self):
        self._stop_process(self.record_process)
        self._stop_process(self.teleop_process)
        self._stop_process(self.joy_process)
        self.record_process = None
        self.record_bag_path = None
        if self.rumble_stop_timer is not None:
            self.rumble_stop_timer.cancel()
            self.rumble_stop_timer = None
        self.teleop_process = None
        self.joy_process = None

    def destroy_node(self):
        self._stop_processes()
        super().destroy_node()


def main(args=None):
    rclpy.init(args=args)
    node = GamepadModeManager()
    try:
        rclpy.spin(node)
    except (KeyboardInterrupt, ExternalShutdownException):
        pass
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == "__main__":
    main()
