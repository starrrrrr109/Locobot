#!/usr/bin/env python3
"""Publish the camera pose in odom at each RGB image timestamp."""

import time

import rclpy
from geometry_msgs.msg import TransformStamped
from rclpy.duration import Duration
from rclpy.executors import ExternalShutdownException, MultiThreadedExecutor
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data
from rclpy.time import Time
from sensor_msgs.msg import CompressedImage
from tf2_ros import Buffer, TransformException, TransformListener


class CameraPoseOdomRelay(Node):
    """Look up odom-to-camera TF at the timestamp carried by each RGB image."""

    def __init__(self):
        super().__init__("camera_pose_odom_relay")

        self.declare_parameter(
            "image_topic", "/locobot/camera/camera/color/image_raw/compressed"
        )
        self.declare_parameter("output_topic", "/locobot/camera_pose_odom")
        self.declare_parameter("target_frame", "locobot/odom")
        self.declare_parameter("lookup_timeout_sec", 0.05)
        self.declare_parameter("warning_throttle_sec", 5.0)

        image_topic = self.get_parameter("image_topic").value
        output_topic = self.get_parameter("output_topic").value
        self._target_frame = self.get_parameter("target_frame").value
        lookup_timeout_sec = self.get_parameter("lookup_timeout_sec").value
        self._warning_throttle_sec = self.get_parameter("warning_throttle_sec").value

        if not self._target_frame:
            raise ValueError("target_frame must not be empty")
        if lookup_timeout_sec < 0.0:
            raise ValueError("lookup_timeout_sec must be non-negative")
        if self._warning_throttle_sec < 0.0:
            raise ValueError("warning_throttle_sec must be non-negative")

        self._lookup_timeout = Duration(seconds=lookup_timeout_sec)
        self._last_warning_time = float("-inf")
        self._tf_buffer = Buffer()
        self._tf_listener = TransformListener(self._tf_buffer, self)
        self._publisher = self.create_publisher(TransformStamped, output_topic, 10)
        self._subscription = self.create_subscription(
            CompressedImage,
            image_topic,
            self._on_image,
            qos_profile_sensor_data,
        )

        self.get_logger().info(
            f"Relaying {image_topic} timestamps to {output_topic}; "
            f"target frame is {self._target_frame}"
        )

    def _warn_throttled(self, message):
        now = time.monotonic()
        if now - self._last_warning_time >= self._warning_throttle_sec:
            self._last_warning_time = now
            self.get_logger().warning(message)

    def _on_image(self, msg):
        source_frame = msg.header.frame_id
        stamp = msg.header.stamp
        stamp_text = f"{stamp.sec}.{stamp.nanosec:09d}"

        if not source_frame:
            self._warn_throttled(
                f"Skipping RGB image at {stamp_text}: source frame_id is empty; "
                f"target={self._target_frame}"
            )
            return

        try:
            transform = self._tf_buffer.lookup_transform(
                self._target_frame,
                source_frame,
                Time.from_msg(stamp),
                timeout=self._lookup_timeout,
            )
        except TransformException as exception:
            self._warn_throttled(
                f"Skipping RGB image at {stamp_text}: TF lookup "
                f"source={source_frame}, target={self._target_frame} failed: {exception}"
            )
            return

        # Preserve the source timestamp exactly. Never replace it with the lookup
        # result's stamp, current time, or the latest available TF timestamp.
        transform.header.stamp = stamp
        transform.header.frame_id = self._target_frame
        transform.child_frame_id = source_frame
        self._publisher.publish(transform)


def main(args=None):
    rclpy.init(args=args)
    node = CameraPoseOdomRelay()
    executor = MultiThreadedExecutor(num_threads=2)
    executor.add_node(node)
    try:
        executor.spin()
    except (KeyboardInterrupt, ExternalShutdownException):
        pass
    finally:
        executor.shutdown()
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == "__main__":
    main()
