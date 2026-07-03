import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch_ros.actions import Node


def generate_launch_description():
    package_share = get_package_share_directory("tennisbot_vision_runtime")
    default_parameters = os.path.join(
        package_share,
        "config",
        "vision_runtime.yaml",
    )

    return LaunchDescription([
        Node(
            package="tennisbot_vision_runtime",
            executable="vision_runtime_node",
            name="vision_runtime",
            output="screen",
            parameters=[default_parameters],
        ),
    ])
