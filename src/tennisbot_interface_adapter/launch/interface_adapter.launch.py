import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    package_share = get_package_share_directory("tennisbot_interface_adapter")
    default_parameters = os.path.join(
        package_share,
        "config",
        "interface_adapter.yaml",
    )

    return LaunchDescription([
        DeclareLaunchArgument("use_sim_time", default_value="false"),
        Node(
            package="tennisbot_interface_adapter",
            executable="vision_interface_adapter_node",
            name="vision_interface_adapter",
            output="screen",
            parameters=[
                default_parameters,
                {"use_sim_time": LaunchConfiguration("use_sim_time")},
            ],
        ),
    ])
