import rclpy
from rclpy.node import Node
from sensor_msgs.msg import PointCloud2

class PointCloudDownsampler(Node):
    def __init__(self):
        super().__init__('pointcloud_downsampler')
        # 設定抽樣間隔 (例如 10 代表每 10 個點取 1 個點，資料量直接減少 90%)
        self.step = 10 
        
        self.sub = self.create_subscription(
            PointCloud2,
            '/mast3r/camera/depth/color/points',
            self.pc_callback,
            10
        )
        self.pub = self.create_publisher(
            PointCloud2,
            '/mast3r/camera/depth/color/points_downsampled',
            10
        )
        self.get_logger().info(f'🚀 點雲降採樣節點已啟動！(每 {self.step} 個點抽取 1 個點)')

    def pc_callback(self, msg: PointCloud2):
        p_step = msg.point_step
        if p_step == 0 or len(msg.data) == 0:
            return

        # 利用 Python memoryview 進行極速 Byte 切片
        raw_data = memoryview(msg.data)
        chunk_size = p_step * self.step
        
        out_bytes = bytearray()
        for i in range(0, len(raw_data) - p_step + 1, chunk_size):
            out_bytes.extend(raw_data[i : i + p_step])

        # 建立降採樣後的 PointCloud2 訊息
        new_msg = PointCloud2()
        new_msg.header = msg.header
        new_msg.height = 1
        new_msg.width = len(out_bytes) // p_step
        new_msg.fields = msg.fields
        new_msg.is_bigendian = msg.is_bigendian
        new_msg.point_step = p_step
        new_msg.row_step = len(out_bytes)
        new_msg.data = bytes(out_bytes)
        new_msg.is_dense = msg.is_dense

        self.pub.publish(new_msg)

def main(args=None):
    rclpy.init(args=args)
    node = PointCloudDownsampler()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()

if __name__ == '__main__':
    main()