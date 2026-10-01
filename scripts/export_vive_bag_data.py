#!/usr/bin/env python3
"""Export VIVE tracker poses and the first camera timestamp from a ROS 2 bag."""

from __future__ import annotations

import argparse
import csv
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple


TRACKER_TOPICS = {
    "tracker1": "/tracker1/vive_pose_abs",
    "tracker2": "/tracker2/vive_pose_abs",
    "tracker3": "/tracker3/vive_pose_abs",
}
TRACKER_TYPE = "geometry_msgs/msg/TransformStamped"
IMAGE_TYPE = "sensor_msgs/msg/CompressedImage"
DEFAULT_IMAGE_TOPIC = "/locobot/camera/camera/color/image_raw/compressed"

CSV_FIELDS = [
    "bag_timestamp_ns",
    "bag_timestamp_sec",
    "header_timestamp_ns",
    "header_timestamp_sec",
    "frame_id",
    "child_frame_id",
    "x",
    "y",
    "z",
    "qx",
    "qy",
    "qz",
    "qw",
]


class ExportError(RuntimeError):
    """An expected, user-facing export failure."""


@dataclass(frozen=True)
class TimestampInfo:
    bag_ns: int
    header_ns: int
    header_is_valid: bool

    @property
    def effective_ns(self) -> int:
        return self.header_ns if self.header_is_valid else self.bag_ns

    @property
    def basis(self) -> str:
        return "header timestamp" if self.header_is_valid else "bag timestamp"


@dataclass(frozen=True)
class PoseRecord:
    timestamp: TimestampInfo
    frame_id: str
    child_frame_id: str
    x: float
    y: float
    z: float
    qx: float
    qy: float
    qz: float
    qw: float


@dataclass(frozen=True)
class ImageRecord:
    timestamp: TimestampInfo
    frame_id: str


def format_sec(timestamp_ns: int) -> str:
    # Avoid converting epoch-scale nanoseconds to float for display: IEEE-754
    # cannot retain every nanosecond at this magnitude.
    sign = "-" if timestamp_ns < 0 else ""
    whole_seconds, remaining_nanoseconds = divmod(abs(timestamp_ns), 1_000_000_000)
    return f"{sign}{whole_seconds}.{remaining_nanoseconds:09d}"


def timestamp_from_message(msg: Any, bag_timestamp_ns: int) -> TimestampInfo:
    stamp = msg.header.stamp
    sec = int(stamp.sec)
    nanosec = int(stamp.nanosec)
    header_ns = sec * 1_000_000_000 + nanosec
    # ROS time zero conventionally means "not set". A malformed nanosecond
    # component is also treated as invalid for matching.
    header_is_valid = header_ns > 0 and 0 <= nanosec < 1_000_000_000
    return TimestampInfo(
        bag_ns=int(bag_timestamp_ns),
        header_ns=header_ns,
        header_is_valid=header_is_valid,
    )


def pose_from_message(msg: Any, bag_timestamp_ns: int) -> PoseRecord:
    translation = msg.transform.translation
    rotation = msg.transform.rotation
    return PoseRecord(
        timestamp=timestamp_from_message(msg, bag_timestamp_ns),
        frame_id=str(msg.header.frame_id),
        child_frame_id=str(msg.child_frame_id),
        x=float(translation.x),
        y=float(translation.y),
        z=float(translation.z),
        qx=float(rotation.x),
        qy=float(rotation.y),
        qz=float(rotation.z),
        qw=float(rotation.w),
    )


def csv_row(record: PoseRecord) -> Dict[str, object]:
    return {
        "bag_timestamp_ns": record.timestamp.bag_ns,
        "bag_timestamp_sec": format_sec(record.timestamp.bag_ns),
        "header_timestamp_ns": record.timestamp.header_ns,
        "header_timestamp_sec": format_sec(record.timestamp.header_ns),
        "frame_id": record.frame_id,
        "child_frame_id": record.child_frame_id,
        "x": record.x,
        "y": record.y,
        "z": record.z,
        "qx": record.qx,
        "qy": record.qy,
        "qz": record.qz,
        "qw": record.qw,
    }


def write_tracker_csv(path: Path, records: Sequence[PoseRecord]) -> None:
    try:
        with path.open("w", newline="", encoding="utf-8") as output_file:
            writer = csv.DictWriter(output_file, fieldnames=CSV_FIELDS)
            writer.writeheader()
            for record in records:
                writer.writerow(csv_row(record))
    except OSError as exc:
        raise ExportError(f"cannot write CSV file '{path}': {exc}") from exc


def nearest_pose(
    records: Sequence[PoseRecord], image: ImageRecord
) -> Optional[Tuple[PoseRecord, int]]:
    if not records:
        return None
    selected = min(
        records,
        key=lambda record: abs(
            record.timestamp.effective_ns - image.timestamp.effective_ns
        ),
    )
    signed_difference_ns = (
        selected.timestamp.effective_ns - image.timestamp.effective_ns
    )
    return selected, signed_difference_ns


def timestamp_lines(prefix: str, timestamp: TimestampInfo) -> List[str]:
    return [
        f"{prefix}_bag_timestamp_ns: {timestamp.bag_ns}",
        f"{prefix}_bag_timestamp_sec: {format_sec(timestamp.bag_ns)}",
        f"{prefix}_header_timestamp_ns: {timestamp.header_ns}",
        f"{prefix}_header_timestamp_sec: {format_sec(timestamp.header_ns)}",
        f"{prefix}_selected_timestamp_basis: {timestamp.basis}",
        f"{prefix}_selected_timestamp_ns: {timestamp.effective_ns}",
        f"{prefix}_selected_timestamp_sec: {format_sec(timestamp.effective_ns)}",
    ]


def write_text(path: Path, lines: Sequence[str]) -> None:
    try:
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    except OSError as exc:
        raise ExportError(f"cannot write output file '{path}': {exc}") from exc


def validate_paths(bag_path: Path, output_path: Path) -> None:
    if not bag_path.exists():
        raise ExportError(f"bag path does not exist: {bag_path}")
    if not bag_path.is_dir():
        raise ExportError(
            f"--bag must be a rosbag2 directory, not a .db3 file: {bag_path}"
        )
    metadata_path = bag_path / "metadata.yaml"
    if not metadata_path.is_file():
        raise ExportError(f"metadata.yaml not found in bag directory: {bag_path}")
    if output_path == bag_path:
        raise ExportError("--output must not be the rosbag2 source directory")

    try:
        output_path.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise ExportError(
            f"cannot create output directory '{output_path}': {exc}"
        ) from exc
    if not output_path.is_dir():
        raise ExportError(f"output path is not a directory: {output_path}")


def open_reader(bag_path: Path) -> Tuple[Any, Dict[str, str]]:
    try:
        import rosbag2_py
    except ImportError as exc:
        raise ExportError(
            "ROS 2 Python module 'rosbag2_py' is unavailable. "
            "Source /opt/ros/humble/setup.bash (and the workspace setup) first."
        ) from exc

    reader = rosbag2_py.SequentialReader()
    storage_options = rosbag2_py.StorageOptions(
        uri=str(bag_path), storage_id="sqlite3"
    )
    converter_options = rosbag2_py.ConverterOptions(
        input_serialization_format="cdr",
        output_serialization_format="cdr",
    )
    try:
        reader.open(storage_options, converter_options)
        topic_types = {
            item.name: item.type for item in reader.get_all_topics_and_types()
        }
    except Exception as exc:
        raise ExportError(f"failed to open rosbag2 '{bag_path}': {exc}") from exc

    return reader, topic_types


def validate_topics(topic_types: Dict[str, str], image_topic: str) -> None:
    expected = {
        **{topic: TRACKER_TYPE for topic in TRACKER_TOPICS.values()},
        image_topic: IMAGE_TYPE,
    }
    for topic, expected_type in expected.items():
        if topic not in topic_types:
            raise ExportError(f"required topic not found in bag: {topic}")
        actual_type = topic_types[topic]
        if actual_type != expected_type:
            raise ExportError(
                f"topic type mismatch for {topic}: expected {expected_type}, "
                f"found {actual_type}"
            )


def read_bag(
    reader: Any, image_topic: str
) -> Tuple[Dict[str, List[PoseRecord]], int, Optional[ImageRecord], Optional[ImageRecord]]:
    try:
        import rosbag2_py
        from rclpy.serialization import deserialize_message
        from rosidl_runtime_py.utilities import get_message
    except ImportError as exc:
        raise ExportError(
            "Required ROS 2 Python modules are unavailable. "
            "Source /opt/ros/humble/setup.bash (and the workspace setup) first."
        ) from exc

    topic_to_tracker = {
        topic: tracker_name for tracker_name, topic in TRACKER_TOPICS.items()
    }
    selected_topics = list(topic_to_tracker) + [image_topic]
    try:
        reader.set_filter(rosbag2_py.StorageFilter(topics=selected_topics))
        tracker_message_class = get_message(TRACKER_TYPE)
        image_message_class = get_message(IMAGE_TYPE)
    except Exception as exc:
        raise ExportError(f"failed to prepare ROS 2 message readers: {exc}") from exc

    trackers: Dict[str, List[PoseRecord]] = {
        tracker_name: [] for tracker_name in TRACKER_TOPICS
    }
    image_count = 0
    first_image: Optional[ImageRecord] = None
    last_image: Optional[ImageRecord] = None

    try:
        while reader.has_next():
            topic, serialized_data, bag_timestamp_ns = reader.read_next()
            if topic in topic_to_tracker:
                msg = deserialize_message(serialized_data, tracker_message_class)
                tracker_name = topic_to_tracker[topic]
                trackers[tracker_name].append(
                    pose_from_message(msg, int(bag_timestamp_ns))
                )
            elif topic == image_topic:
                msg = deserialize_message(serialized_data, image_message_class)
                image_record = ImageRecord(
                    timestamp=timestamp_from_message(msg, int(bag_timestamp_ns)),
                    frame_id=str(msg.header.frame_id),
                )
                image_count += 1
                if first_image is None:
                    first_image = image_record
                last_image = image_record
    except Exception as exc:
        raise ExportError(f"failed while reading rosbag2 data: {exc}") from exc

    return trackers, image_count, first_image, last_image


def describe_topic_range(
    topic: str, records: Sequence[PoseRecord]
) -> List[str]:
    lines = [f"topic: {topic}", f"message_count: {len(records)}"]
    if not records:
        lines.append("first_timestamp: unavailable (topic has no messages)")
        lines.append("last_timestamp: unavailable (topic has no messages)")
        return lines
    lines.extend(timestamp_lines("first", records[0].timestamp))
    lines.extend(timestamp_lines("last", records[-1].timestamp))
    return lines


def write_first_image_file(
    output_path: Path, image_topic: str, image: ImageRecord
) -> None:
    lines = [
        f"image_topic: {image_topic}",
        f"bag_timestamp_ns: {image.timestamp.bag_ns}",
        f"bag_timestamp_sec: {format_sec(image.timestamp.bag_ns)}",
        f"header_timestamp_ns: {image.timestamp.header_ns}",
        f"header_timestamp_sec: {format_sec(image.timestamp.header_ns)}",
        f"header_frame_id: {image.frame_id}",
        f"selected_timestamp_basis: {image.timestamp.basis}",
        f"selected_timestamp_ns: {image.timestamp.effective_ns}",
        f"selected_timestamp_sec: {format_sec(image.timestamp.effective_ns)}",
    ]
    write_text(output_path / "first_image_timestamp.txt", lines)


def pose_detail_lines(
    tracker_name: str,
    pose: PoseRecord,
    image: ImageRecord,
    signed_difference_ns: int,
) -> List[str]:
    return [
        f"tracker: {tracker_name}",
        f"selected timestamp basis: tracker={pose.timestamp.basis}; "
        f"first_image={image.timestamp.basis}",
        f"{tracker_name} timestamp ns: {pose.timestamp.effective_ns}",
        f"{tracker_name} timestamp sec: {format_sec(pose.timestamp.effective_ns)}",
        f"first image timestamp ns: {image.timestamp.effective_ns}",
        f"first image timestamp sec: {format_sec(image.timestamp.effective_ns)}",
        f"time difference sec (tracker - image): {signed_difference_ns / 1e9:.9f}",
        f"absolute time difference sec: {abs(signed_difference_ns) / 1e9:.9f}",
        f"translation: x={pose.x}, y={pose.y}, z={pose.z}",
        f"quaternion: x={pose.qx}, y={pose.qy}, z={pose.qz}, w={pose.qw}",
        f"frame_id: {pose.frame_id}",
        f"child_frame_id: {pose.child_frame_id}",
        f"tracker bag timestamp ns: {pose.timestamp.bag_ns}",
        f"tracker header timestamp ns: {pose.timestamp.header_ns}",
        f"first image bag timestamp ns: {image.timestamp.bag_ns}",
        f"first image header timestamp ns: {image.timestamp.header_ns}",
    ]


def write_summary(
    output_path: Path,
    bag_path: Path,
    image_topic: str,
    trackers: Dict[str, List[PoseRecord]],
    image_count: int,
    first_image: ImageRecord,
    last_image: ImageRecord,
    nearest: Dict[str, Optional[Tuple[PoseRecord, int]]],
) -> None:
    lines = [f"bag path: {bag_path}", ""]
    for tracker_name, topic in TRACKER_TOPICS.items():
        lines.append(f"[{tracker_name}]")
        lines.extend(describe_topic_range(topic, trackers[tracker_name]))
        lines.append("")

    lines.extend(
        [
            "[camera]",
            f"topic: {image_topic}",
            f"message_count: {image_count}",
        ]
    )
    lines.extend(timestamp_lines("first", first_image.timestamp))
    lines.extend(timestamp_lines("last", last_image.timestamp))
    lines.extend(
        [
            f"first_header_frame_id: {first_image.frame_id}",
            "",
            "[nearest poses to first image]",
            f"first_image_selected_timestamp_basis: {first_image.timestamp.basis}",
            f"first_image_selected_timestamp_ns: "
            f"{first_image.timestamp.effective_ns}",
            f"first_image_selected_timestamp_sec: "
            f"{format_sec(first_image.timestamp.effective_ns)}",
        ]
    )

    for tracker_name in TRACKER_TOPICS:
        match = nearest[tracker_name]
        lines.append("")
        lines.append(f"{tracker_name}:")
        if match is None:
            lines.append("  nearest_pose: unavailable (topic has no messages)")
            continue
        pose, difference_ns = match
        lines.extend(
            [
                f"  tracker_selected_timestamp_basis: {pose.timestamp.basis}",
                f"  tracker_selected_timestamp_ns: {pose.timestamp.effective_ns}",
                f"  tracker_selected_timestamp_sec: "
                f"{format_sec(pose.timestamp.effective_ns)}",
                f"  signed_time_difference_sec (tracker - image): "
                f"{difference_ns / 1e9:.9f}",
                f"  absolute_time_difference_sec: "
                f"{abs(difference_ns) / 1e9:.9f}",
                f"  translation: x={pose.x}, y={pose.y}, z={pose.z}",
                f"  quaternion: x={pose.qx}, y={pose.qy}, z={pose.qz}, "
                f"w={pose.qw}",
                f"  frame_id: {pose.frame_id}",
                f"  child_frame_id: {pose.child_frame_id}",
            ]
        )

    write_text(output_path / "summary.txt", lines)


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Export three VIVE TransformStamped topics and the first compressed "
            "camera timestamp from a ROS 2 Humble sqlite3 bag."
        )
    )
    parser.add_argument(
        "--bag",
        required=True,
        type=Path,
        help="rosbag2 directory containing metadata.yaml and .db3 file(s)",
    )
    parser.add_argument(
        "--output",
        required=True,
        type=Path,
        help="directory for tracker CSV and timestamp/summary text files",
    )
    parser.add_argument(
        "--image-topic",
        default=DEFAULT_IMAGE_TOPIC,
        help=f"compressed image topic (default: {DEFAULT_IMAGE_TOPIC})",
    )
    return parser.parse_args(argv)


def run(args: argparse.Namespace) -> int:
    bag_path = args.bag.expanduser().resolve()
    output_path = args.output.expanduser().resolve()
    image_topic = str(args.image_topic)
    if not image_topic.startswith("/"):
        raise ExportError("--image-topic must be an absolute ROS topic name")

    validate_paths(bag_path, output_path)
    reader, topic_types = open_reader(bag_path)
    validate_topics(topic_types, image_topic)
    trackers, image_count, first_image, last_image = read_bag(
        reader, image_topic
    )

    for tracker_name, records in trackers.items():
        write_tracker_csv(output_path / f"{tracker_name}.csv", records)

    if first_image is None or last_image is None:
        raise ExportError(f"bag contains no messages on image topic: {image_topic}")

    write_first_image_file(output_path, image_topic, first_image)
    nearest = {
        tracker_name: nearest_pose(records, first_image)
        for tracker_name, records in trackers.items()
    }
    write_summary(
        output_path,
        bag_path,
        image_topic,
        trackers,
        image_count,
        first_image,
        last_image,
        nearest,
    )

    tracker2_match = nearest["tracker2"]
    if tracker2_match is None:
        write_text(
            output_path / "tracker2_at_first_image.txt",
            [
                "tracker: tracker2",
                "nearest_pose: unavailable (topic has no messages)",
                f"first image timestamp ns: "
                f"{first_image.timestamp.effective_ns}",
                f"first image timestamp sec: "
                f"{format_sec(first_image.timestamp.effective_ns)}",
                f"first image selected timestamp basis: "
                f"{first_image.timestamp.basis}",
            ],
        )
    else:
        tracker2_pose, tracker2_difference_ns = tracker2_match
        write_text(
            output_path / "tracker2_at_first_image.txt",
            pose_detail_lines(
                "tracker2",
                tracker2_pose,
                first_image,
                tracker2_difference_ns,
            ),
        )

    print("Export complete")
    for tracker_name in TRACKER_TOPICS:
        print(f"{tracker_name}: {len(trackers[tracker_name])} messages")
    print(f"images: {image_count} messages")
    print(
        "first image timestamp: "
        f"{format_sec(first_image.timestamp.effective_ns)} sec "
        f"({first_image.timestamp.basis})"
    )
    if tracker2_match is None:
        print("nearest tracker2 time difference: unavailable")
    else:
        print(
            "nearest tracker2 time difference: "
            f"{abs(tracker2_match[1]) / 1e9:.9f} sec"
        )

    empty_trackers = [
        tracker_name
        for tracker_name, records in trackers.items()
        if not records
    ]
    for tracker_name in empty_trackers:
        print(
            f"Warning: {TRACKER_TOPICS[tracker_name]} has no messages",
            file=sys.stderr,
        )
    return 0


def main(argv: Optional[Sequence[str]] = None) -> int:
    try:
        args = parse_args(argv)
        return run(args)
    except ExportError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("Error: interrupted", file=sys.stderr)
        return 130


if __name__ == "__main__":
    sys.exit(main())
