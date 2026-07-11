from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node
import math

# 将度数转换为弧度的辅助函数
def deg_to_rad(degrees):
    return degrees * math.pi / 180.0

def generate_launch_description():
    return LaunchDescription([
        DeclareLaunchArgument(
            name='scanner', default_value='scanner',
            description='Namespace for sample topics'
        ),
        Node(
            package='pointcloud_to_laserscan', executable='pointcloud_to_laserscan_node',
            remappings=[('cloud', [LaunchConfiguration(variable_name='scanner'), '/cloud']),
                        ('scan', [LaunchConfiguration(variable_name='scanner'), '/scan'])],
        parameters=[{
                'target_frame': 'base_link',
                'transform_tolerance': 0.01,
                'min_height': 0.10,
                'max_height': 1.5,
                'angle_min': -3.141592654,  # -M_PI/2
                'angle_max': 3.141592654,  # M_PI/2
                'angle_increment': 0.003141592,  # M_PI/360.0
                'scan_time': 0.2,
                'range_min': 0.3,
                'range_max': 40.0,
                'use_inf': True,
                'inf_epsilon': 1.0
            }],
            name='pointcloud_to_laserscan'
        )
    ])
