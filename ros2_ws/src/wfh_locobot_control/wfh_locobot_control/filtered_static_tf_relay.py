#!/usr/bin/env python3
"""Periodically relay selected Locobot static TF edges on a normal topic."""

import argparse

import rclpy
from rclpy.executors import ExternalShutdownException
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy, HistoryPolicy, QoSProfile, ReliabilityPolicy
from rclpy.utilities import remove_ros_args
from tf2_msgs.msg import TFMessage


DEFAULT_EDGES = (
    ("locobot/base_footprint", "locobot/base_link"),
    ("locobot/base_link", "locobot/apriltag_link"),
)


def normalize_frame_id(frame_id):
    return frame_id.lstrip("/")


def key_for_transform(transform):
    return (
        normalize_frame_id(transform.header.frame_id),
        normalize_frame_id(transform.child_frame_id),
    )


class FilteredStaticTfRelay(Node):
    def __init__(self, input_topic, output_topic, rate_hz, allowed_edges):
        super().__init__("locobot_filtered_static_tf_relay")
        if rate_hz <= 0.0:
            raise ValueError("rate_hz must be greater than 0")

        self.allowed_edges = {
            (normalize_frame_id(parent), normalize_frame_id(child))
            for parent, child in allowed_edges
        }
        self.cache = {}

        static_qos = QoSProfile(
            history=HistoryPolicy.KEEP_LAST,
            depth=100,
            reliability=ReliabilityPolicy.RELIABLE,
            durability=DurabilityPolicy.TRANSIENT_LOCAL,
        )
        relay_qos = QoSProfile(
            history=HistoryPolicy.KEEP_LAST,
            depth=10,
            reliability=ReliabilityPolicy.RELIABLE,
            durability=DurabilityPolicy.VOLATILE,
        )

        self.sub = self.create_subscription(TFMessage, input_topic, self.on_static_tf, static_qos)
        self.pub = self.create_publisher(TFMessage, output_topic, relay_qos)
        self.timer = self.create_timer(1.0 / rate_hz, self.publish_cache)

        edge_list = ", ".join(f"{parent}->{child}" for parent, child in sorted(self.allowed_edges))
        self.get_logger().info(
            f"Relaying selected static TF from {input_topic} to {output_topic} "
            f"at {rate_hz:.2f} Hz: {edge_list}"
        )

    def on_static_tf(self, msg):
        updated = False
        for transform in msg.transforms:
            key = key_for_transform(transform)
            if key not in self.allowed_edges:
                continue

            self.cache[key] = transform
            updated = True

        if updated:
            self.get_logger().info(
                f"Cached {len(self.cache)}/{len(self.allowed_edges)} selected static TF edges"
            )
            self.publish_cache()

    def publish_cache(self):
        if not self.cache:
            return

        msg = TFMessage()
        msg.transforms = [self.cache[key] for key in sorted(self.cache)]
        self.pub.publish(msg)


def parse_args(args=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-topic", default="/tf_static")
    parser.add_argument("--output-topic", default="/locobot/static_tf_relay")
    parser.add_argument("--rate", type=float, default=2.0)
    parser.add_argument(
        "--edge",
        nargs=2,
        action="append",
        metavar=("PARENT_FRAME", "CHILD_FRAME"),
        help="Static TF edge to relay. Can be used multiple times.",
    )
    parsed = parser.parse_args(remove_ros_args(args=args)[1:])
    if parsed.edge is None:
        parsed.edge = list(DEFAULT_EDGES)
    return parsed


def main(args=None):
    parsed_args = parse_args(args)

    rclpy.init(args=args)
    node = FilteredStaticTfRelay(
        parsed_args.input_topic,
        parsed_args.output_topic,
        parsed_args.rate,
        parsed_args.edge,
    )
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
