#!/usr/bin/env python3

import cv2
import message_filters
import numpy as np
import rclpy
from rclpy.node import Node
from rclpy.qos import HistoryPolicy, QoSProfile, ReliabilityPolicy
from sensor_msgs.msg import CompressedImage, Image


class TripleCameraFusionNode(Node):
    def __init__(self) -> None:
        super().__init__('triple_camera_fusion')

        self.declare_parameter('camera1_topic', '/camera_1/camera/color/image_raw')
        self.declare_parameter('camera2_topic', '/camera_2/camera/color/image_raw')
        self.declare_parameter('camera3_topic', '/camera_3/camera/color/image_raw')
        self.declare_parameter(
            'output_topic',
            '/locobot/camera/camera/color/image_raw/compressed/fusion',
        )
        self.declare_parameter('jpeg_quality', 90)
        self.declare_parameter('overlap_px', 80)
        self.declare_parameter('sync_queue_size', 30)
        self.declare_parameter('sync_slop_sec', 0.03)
        self.declare_parameter('enable_geometric_correction', True)
        self.declare_parameter(
            'cam1_homography',
            [
                1.0,
                0.0,
                0.0,
                0.0,
                1.0,
                0.0,
                0.0,
                0.0,
                1.0,
            ],
        )
        self.declare_parameter(
            'cam2_homography',
            [
                1.0,
                0.0,
                0.0,
                0.0,
                1.0,
                0.0,
                0.0,
                0.0,
                1.0,
            ],
        )
        self.declare_parameter(
            'cam3_homography',
            [
                1.0,
                0.0,
                0.0,
                0.0,
                1.0,
                0.0,
                0.0,
                0.0,
                1.0,
            ],
        )

        camera1_topic = self.get_parameter('camera1_topic').get_parameter_value().string_value
        camera2_topic = self.get_parameter('camera2_topic').get_parameter_value().string_value
        camera3_topic = self.get_parameter('camera3_topic').get_parameter_value().string_value
        self.output_topic = self.get_parameter('output_topic').get_parameter_value().string_value
        self.jpeg_quality = int(self.get_parameter('jpeg_quality').get_parameter_value().integer_value)
        self.overlap_px = int(self.get_parameter('overlap_px').get_parameter_value().integer_value)
        sync_queue_size = int(self.get_parameter('sync_queue_size').get_parameter_value().integer_value)
        sync_slop_sec = float(self.get_parameter('sync_slop_sec').get_parameter_value().double_value)
        self.enable_geometric_correction = bool(
            self.get_parameter('enable_geometric_correction').get_parameter_value().bool_value
        )
        self.cam1_h = self._read_homography('cam1_homography')
        self.cam2_h = self._read_homography('cam2_homography')
        self.cam3_h = self._read_homography('cam3_homography')

        sensor_qos = QoSProfile(
            reliability=ReliabilityPolicy.BEST_EFFORT,
            history=HistoryPolicy.KEEP_LAST,
            depth=10,
        )

        self.sub_cam1 = message_filters.Subscriber(self, Image, camera1_topic, qos_profile=sensor_qos)
        self.sub_cam2 = message_filters.Subscriber(self, Image, camera2_topic, qos_profile=sensor_qos)
        self.sub_cam3 = message_filters.Subscriber(self, Image, camera3_topic, qos_profile=sensor_qos)

        self.sync = message_filters.ApproximateTimeSynchronizer(
            [self.sub_cam1, self.sub_cam2, self.sub_cam3],
            queue_size=sync_queue_size,
            slop=sync_slop_sec,
            allow_headerless=False,
        )
        self.sync.registerCallback(self.synced_callback)

        self.publisher = self.create_publisher(CompressedImage, self.output_topic, 10)

        self.get_logger().info(
            f'Triple camera fusion started. Inputs: [{camera1_topic}, {camera2_topic}, {camera3_topic}], '
            f'output: {self.output_topic}'
        )

    def _read_homography(self, parameter_name: str) -> np.ndarray:
        values = self.get_parameter(parameter_name).get_parameter_value().double_array_value
        if len(values) != 9:
            self.get_logger().warn(
                f'Parameter {parameter_name} must have 9 values. Fallback to identity.',
                throttle_duration_sec=5.0,
            )
            return np.eye(3, dtype=np.float32)
        return np.array(values, dtype=np.float32).reshape((3, 3))

    def apply_fixed_geometry(self, image: np.ndarray, homography: np.ndarray) -> np.ndarray:
        h, w = image.shape[:2]
        return cv2.warpPerspective(
            image,
            homography,
            (w, h),
            flags=cv2.INTER_LINEAR,
            borderMode=cv2.BORDER_CONSTANT,
            borderValue=(0, 0, 0),
        )

    def image_to_bgr(self, msg: Image):
        if msg.height == 0 or msg.width == 0:
            return None

        data = np.frombuffer(msg.data, dtype=np.uint8)
        step = int(msg.step)

        if step <= 0 or data.size < msg.height * step:
            return None

        row_major = data[: msg.height * step].reshape((msg.height, step))

        if msg.encoding in ('rgb8', 'bgr8'):
            width_bytes = msg.width * 3
            if step < width_bytes:
                return None
            image = row_major[:, :width_bytes].reshape((msg.height, msg.width, 3))
            if msg.encoding == 'rgb8':
                image = cv2.cvtColor(image, cv2.COLOR_RGB2BGR)
            return image

        if msg.encoding in ('rgba8', 'bgra8'):
            width_bytes = msg.width * 4
            if step < width_bytes:
                return None
            image = row_major[:, :width_bytes].reshape((msg.height, msg.width, 4))
            if msg.encoding == 'rgba8':
                return cv2.cvtColor(image, cv2.COLOR_RGBA2BGR)
            return cv2.cvtColor(image, cv2.COLOR_BGRA2BGR)

        if msg.encoding == 'mono8':
            if step < msg.width:
                return None
            image = row_major[:, : msg.width].reshape((msg.height, msg.width))
            return cv2.cvtColor(image, cv2.COLOR_GRAY2BGR)

        self.get_logger().warn('Unsupported encoding: %s', msg.encoding, throttle_duration_sec=5.0)
        return None

    @staticmethod
    def feather_blend(left: np.ndarray, right: np.ndarray, overlap_px: int) -> np.ndarray:
        overlap_px = max(0, min(overlap_px, left.shape[1] - 1, right.shape[1] - 1))
        if overlap_px == 0:
            return np.hstack([left, right])

        left_keep = left[:, :-overlap_px]
        left_overlap = left[:, -overlap_px:].astype(np.float32)
        right_overlap = right[:, :overlap_px].astype(np.float32)
        right_keep = right[:, overlap_px:]

        alpha = np.linspace(0.0, 1.0, overlap_px, dtype=np.float32)
        alpha = alpha.reshape((1, overlap_px, 1))

        blend = (left_overlap * (1.0 - alpha) + right_overlap * alpha).astype(np.uint8)
        return np.hstack([left_keep, blend, right_keep])

    def normalize_heights(self, images):
        target_h = min(img.shape[0] for img in images)
        normalized = []
        for image in images:
            if image.shape[0] == target_h:
                normalized.append(image)
                continue
            scale = target_h / float(image.shape[0])
            resized_w = max(1, int(image.shape[1] * scale))
            resized = cv2.resize(image, (resized_w, target_h), interpolation=cv2.INTER_LINEAR)
            normalized.append(resized)
        return normalized

    def synced_callback(self, msg1: Image, msg2: Image, msg3: Image) -> None:
        img1 = self.image_to_bgr(msg1)
        img2 = self.image_to_bgr(msg2)
        img3 = self.image_to_bgr(msg3)

        if img1 is None or img2 is None or img3 is None:
            return

        img1, img2, img3 = self.normalize_heights([img1, img2, img3])

        if self.enable_geometric_correction:
            img1 = self.apply_fixed_geometry(img1, self.cam1_h)
            img2 = self.apply_fixed_geometry(img2, self.cam2_h)
            img3 = self.apply_fixed_geometry(img3, self.cam3_h)

        fused_12 = self.feather_blend(img1, img2, self.overlap_px)
        fused = self.feather_blend(fused_12, img3, self.overlap_px)

        encode_params = [int(cv2.IMWRITE_JPEG_QUALITY), int(np.clip(self.jpeg_quality, 1, 100))]
        ok, encoded = cv2.imencode('.jpg', fused, encode_params)
        if not ok:
            self.get_logger().warn('JPEG encode failed.', throttle_duration_sec=2.0)
            return

        out = CompressedImage()
        out.header = msg1.header
        out.format = 'jpeg'
        out.data = encoded.tobytes()
        self.publisher.publish(out)


def main(args=None) -> None:
    rclpy.init(args=args)
    node = TripleCameraFusionNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
