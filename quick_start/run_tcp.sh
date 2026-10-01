# 設定 TCP 監聽 IP 與 Port (可透過環境變數帶入預設值)
ROS_IP="${ROS_IP:-0.0.0.0}"
ROS_PORT="${ROS_PORT:-10000}"

echo "=================================================="
echo "🚀 啟動 ROS-TCP-Endpoint 服務 (Unity 通訊)"
echo "📌 監聽 IP: ${ROS_IP}"
echo "📌 監聽 Port: ${ROS_PORT}"
echo "=================================================="

# 執行 TCP Endpoint 節點
ros2 run ros_tcp_endpoint default_server_endpoint \
  --ros-args \
  -p ROS_IP:="${ROS_IP}" \
  -p ROS_PORT:=${ROS_PORT}