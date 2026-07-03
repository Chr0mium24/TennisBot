import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    package_share = get_package_share_directory("tennisbot_headless_vision")
    default_parameters = os.path.join(
        package_share,
        "config",
        "headless_vision.yaml",
    )

    return LaunchDescription([
        DeclareLaunchArgument("use_sim_time", default_value="false"),
        Node(
            package="tennisbot_headless_vision",
            executable="headless_vision_node",
            name="headless_vision",
            output="screen",
            parameters=[
                default_parameters,
                {"use_sim_time": LaunchConfiguration("use_sim_time")},
            ],
        ),
    ])
