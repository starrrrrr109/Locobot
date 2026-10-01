import rclpy
import time
import os
import signal
from std_msgs.msg import Bool, Empty
from std_srvs.srv import Trigger
from sensor_msgs.msg import JointState
from rclpy.signals import SignalHandlerOptions

from interbotix_common_modules.common_robot.robot import InterbotixRobotNode
from interbotix_xs_modules.xs_robot.locobot import InterbotixLocobotXS

class VRArmNode(InterbotixRobotNode):
    def __init__(self):
        super().__init__(node_name='vr_arm_control')
        self.stop_requested = False
        self.get_logger().info('Initializing VR Arm Control Node...')

        robot_model = os.getenv('LOCOBOT_ARM_MODEL', 'locobot_wx200')
        robot_name = os.getenv('LOCOBOT_NAME', 'locobot')
        arm_model = os.getenv('LOCOBOT_MOBILE_ARM_MODEL', 'mobile_wx200')

        self.bot = InterbotixLocobotXS(
            robot_model=robot_model,
            arm_model=arm_model,
            robot_name=robot_name,
            node=self,
        )
        
        self.sub_primary = self.create_subscription(
            Bool, '/vr/right/primarybutton', self.primarybutton_callback, 1)
        self.sub_jointstate = self.create_subscription(
            JointState, '/joint_states_test', self.jointstate_callback, 1)

        self.pub_gripper_open = self.create_publisher(Empty, '/gripper/open', 1)
        self.pub_gripper_close = self.create_publisher(Empty, '/gripper/close', 1)

        self.srv_initial = self.create_service(Trigger, '/initial', self.initial_callback)
        self.srv_calibration = self.create_service(Trigger, '/calibration', self.calibration_callback)
        self.srv_switch = self.create_service(Trigger, '/switch_clockwise', self.switch_clockwise_callback)
        self.srv_resting = self.create_service(Trigger, '/resting', self.resting_callback)

        self.joint = JointState()
        
        self.bot.arm.go_to_home_pose()
        self.get_logger().info(
            'VR Arm Control initialized and homed. model={} arm_model={}'.format(
                robot_model,
                arm_model
            )
        )

    def move_to_resting_pose(self):
        try:
            if rclpy.ok():
                self.get_logger().warning('Shutdown requested. Moving arm to resting pose...')
            self.bot.arm.go_to_sleep_pose()
            if rclpy.ok():
                self.get_logger().warning('Arm is now in resting pose.')
            return True
        except Exception as e:
            if rclpy.ok():
                self.get_logger().error('Failed to move arm to resting pose: {}'.format(e))
            else:
                print('Failed to move arm to resting pose: {}'.format(e))
            return False

    def resting_callback(self, request, response):
        del request
        success = self.move_to_resting_pose()
        response.success = success
        if success:
            response.message = 'Moved to resting pose'
        else:
            response.message = 'Failed to move to resting pose'
        return response

    def initial_callback(self, request, response):
        try:
            self.bot.arm.go_to_home_pose()
            response.success = True
            response.message = 'Moved to home position'
        except Exception as e:
            response.success = False
            response.message = str(e)
            self.get_logger().error('Service call failed: {}'.format(e))
        return response

    def calibration_callback(self, request, response):
        try:
            target_joints = [0.0337, -0.2653, 1.4051, -1.1627, -0.0690]
            self.bot.arm.set_joint_positions(target_joints, blocking=False)
            response.success = True
            response.message = 'Calibrated'
        except Exception as e:
            response.success = False
            response.message = str(e)
            self.get_logger().error('Service call failed: {}'.format(e))
        return response
    
    def switch_clockwise_callback(self, request, response):
        try:
            rounds = 3
            if len(self.joint.position) >= 7:
                joint_1 = self.joint.position[2]
                joint_2 = self.joint.position[3]
                joint_3 = self.joint.position[4]
                joint_4 = self.joint.position[5]
                joint_5 = self.joint.position[6]
            else:
                joint_positions = self.bot.arm.get_joint_commands()
                joint_1, joint_2, joint_3, joint_4, joint_5 = joint_positions[0:5]

            if not (joint_3 < -1.3 and joint_2 < -0.3):
                for i in range(rounds):  
                    self.get_logger().info('round: {}'.format(i))

                    self.gripper_close()
                    time.sleep(2)

                    target_joints = [joint_1, joint_2, joint_3, joint_4, joint_5 + 1.57]
                    self.bot.arm.set_joint_positions(target_joints, blocking=False)
                    self.get_logger().info('screw (turn)')
                    time.sleep(1)
                    
                    self.gripper_open()
                    time.sleep(1)

                    target_joints = [joint_1, joint_2, joint_3, joint_4, joint_5]
                    self.bot.arm.set_joint_positions(target_joints, blocking=False)
                    self.get_logger().info('screw (return)')
                    time.sleep(1)
                    
                    self.gripper_close()
                    time.sleep(1)

                target_joints = [joint_1+0.0436, joint_2-0.1744, joint_3, joint_4+0.2616, joint_5]
                self.bot.arm.set_joint_positions(target_joints, blocking=False)
                self.get_logger().info('take out')
                
            response.success = True
            response.message = 'Switched clockwise'
        except Exception as e:
            response.success = False
            response.message = str(e)
            self.get_logger().error('Service call failed: {}'.format(e))

        return response

    def gripper_close(self):
        self.get_logger().info('close')
        msg = Empty()
        self.pub_gripper_close.publish(msg)

    def gripper_open(self):
        self.get_logger().info('open')
        msg = Empty()
        self.pub_gripper_open.publish(msg)

    def primarybutton_callback(self, msg):
        if msg.data:
            self.gripper_open()
        else:
            self.gripper_close()        

    def jointstate_callback(self, msg):
        self.joint = msg

def main(args=None):
    rclpy.init(args=args, signal_handler_options=SignalHandlerOptions.NO)
    node = None
    try:
        node = VRArmNode()

        def _handle_sigint(signum, frame):
            if node is not None:
                node.stop_requested = True

        signal.signal(signal.SIGINT, _handle_sigint)

        while rclpy.ok() and not node.stop_requested:
            rclpy.spin_once(node, timeout_sec=0.2)

        if node.stop_requested:
            node.move_to_resting_pose()
    except Exception as e:
        import traceback
        traceback.print_exc()
        print('Error initializing node: {}'.format(e))
    finally:
        if node is not None:
            node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()

if __name__ == '__main__':
    main()
