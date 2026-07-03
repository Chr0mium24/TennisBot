import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    package_share = get_package_share_directory("target_manager")
    default_parameters = os.path.join(
        package_share,
        "config",
        "target_manager.yaml",
    )

    return LaunchDescription([
        DeclareLaunchArgument("use_sim_time", default_value="false"),
        Node(
            package="target_manager",
            executable="chassis_position_publisher_node",
            name="chassis_position_publisher",
            output="screen",
            parameters=[
                default_parameters,
                {"use_sim_time": LaunchConfiguration("use_sim_time")},
            ],
        ),
    ])
