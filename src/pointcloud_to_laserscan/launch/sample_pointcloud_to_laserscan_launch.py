from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node
import math # 导入 math 库用于计算弧度

def generate_launch_description():
    # 定义你的点云输入话题的命名空间参数
    scanner_namespace = DeclareLaunchArgument(
        name='scanner',
        default_value='scanner',
        description='Namespace for sample topics'
    )

    # 将度数转换为弧度的辅助函数
    def deg_to_rad(degrees):
        return degrees * math.pi / 180.0

    # --- 范围 1: 170度 ~ 180度 ---
    node_range1 = Node(
        package='pointcloud_to_laserscan',
        executable='pointcloud_to_laserscan_node',
        remappings=[('cloud_in', [LaunchConfiguration(variable_name='scanner'), '/cloud']),
                    ('scan', [LaunchConfiguration(variable_name='scanner'), '/scan'])],
        parameters=[{
            'target_frame': 'unilidar_lidar',
            'transform_tolerance': 0.01,
            'min_height': 0.05,
            'max_height': 1.0,
            'angle_min': deg_to_rad(-179.0),
            'angle_max': deg_to_rad(180.0),
            'angle_increment': 0.0087,
            'scan_time': 0.2,
            'range_min': 0.03,
            'range_max': 20.0,
            'use_inf': True,
            'inf_epsilon': 1.0
        }],
        name='pointcloud_to_laserscan_range170_180'
    )


    return LaunchDescription([
        scanner_namespace,
        node_range1,
        # 添加其他你需要的节点或动作
    ])
