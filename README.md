# Locobot ROS 2 Humble Startup Guide (User Guide)

This guide describes the current, validated startup flow for Locobot in this repository.

## Prerequisites (Enter the Container)
Run all commands inside the dedicated Docker container:

```bash
./run.sh
```

After entering, your prompt should switch to the container user (for example, `root` or `locobot`).

---

## Current Runtime Status

The current active setup is:

- Robot model: `locobot_wx200`
- Base: `kobuki`
- Camera: enabled
- Arm: enabled and controllable
- Safety shutdown linkage: enabled between `terminal1_ros2.sh` and `terminal2_ros2.sh`

---

## Startup Steps (Current Production Flow)

### 1. Start core drivers (base + arm + camera)

Open Terminal 1 and run:

```bash
bash /workspace/quick_start/terminal1_ros2.sh
```

What this does:

- launches `interbotix_xslocobot_control`
- uses `robot_model:=locobot_wx200`
- uses `base_type:=kobuki`
- loads `locobot_wx200` motor config

### 2. Start VR arm control node

Open Terminal 2 and run:

```bash
bash /workspace/quick_start/terminal2_ros2.sh
```

What this does:

- runs `ros2 run wfh_vr_control vrarm`
- exports model env vars:
    - `LOCOBOT_ARM_MODEL=locobot_wx200`
    - `LOCOBOT_MOBILE_ARM_MODEL=mobile_wx200`
- arm moves to starting pose (`go_to_home_pose`) on startup

### 3. Start RosBridge server (Unity data transport)

Open Terminal 3 and run:

```bash
bash /workspace/quick_start/terminal5_ros2.sh
```

---

## Arm Safety Behavior (Important)

### Terminal 2 local protection

When `Ctrl+C` is pressed in Terminal 2:

1. The node catches `SIGINT` manually
2. Arm moves to resting pose (`go_to_sleep_pose`)
3. ROS node is shut down

### Terminal 1 linked protection

When `Ctrl+C` (or `TERM`) is received in Terminal 1:

1. Terminal 1 calls service `/resting` (`std_srvs/srv/Trigger`)
2. Terminal 2 arm node moves arm to resting pose
3. Terminal 1 then stops the core launch process
---

## Model Switch Notes (If Needed)

If you change to another arm model (for example `wx250s`), update these together:

- `quick_start/terminal1_ros2.sh`
- `quick_start/terminal2_ros2.sh`
- matching motor config path

Keep `LOCOBOT_ARM_MODEL` and `LOCOBOT_MOBILE_ARM_MODEL` consistent with the launch model.

---

## Added: Unity Multi-Robot Connection Recommendation (ROSBridge 9091)

For multi-robot concurrent connections, use a dedicated rosbridge port to avoid conflicts with other devices.

### Start RosBridge on Port 9091
Open a terminal and run:

```bash
bash /workspace/quick_start/terminal5_ros2_9091.sh
```

This script is equivalent to:

```bash
ros2 launch rosbridge_server rosbridge_websocket_launch.xml \
    port:=9091 \
    max_message_size:=100000000
```

---

## Added: Unity Topic Mapping (Currently Available)

### Odometry (Subscribe)
- Topic: `/locobot/odom`
- Type: `nav_msgs/msg/Odometry`
- Recommended Unity script: `OdometrySubscriber.cs`

### Base Velocity Command (Publish)
- Topic: `/locobot/commands/velocity`
- Type: `geometry_msgs/msg/Twist`
- Unity recommendation: custom Twist publisher

---

## Added: Camera Pan/Tilt Home Position

Use the following script to return both camera motors to the home position:

```bash
bash /workspace/quick_start/camera_go_home_ros2.sh
```

Internally, it publishes:

```bash
ros2 topic pub --once /locobot/commands/joint_group \
    interbotix_xs_msgs/msg/JointGroupCommand "{name: camera, cmd: [0.0, 0.0]}"
```

---

## Added: Multi-Robot TF Notes

If you have multiple robots, the following is recommended:

1. Use a different `ROS_DOMAIN_ID` per robot
2. Use a different rosbridge port per robot (for example, 9090 / 9091)
3. Ensure frame names use prefixes (for example, `locobot/...`)

This reduces topic/frame conflicts and stays compatible with the standard tf2 ecosystem.
# Locobot
