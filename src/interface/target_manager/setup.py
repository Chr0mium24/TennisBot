from setuptools import find_packages, setup


package_name = "target_manager"


setup(
    name=package_name,
    version="0.1.0",
    packages=find_packages(),
    data_files=[
        ("share/ament_index/resource_index/packages", ["resource/" + package_name]),
        ("share/" + package_name, ["package.xml"]),
        ("share/" + package_name + "/config", ["config/target_manager.yaml"]),
        (
            "share/" + package_name + "/launch",
            [
                "launch/target_manager.launch.py",
                "launch/chassis_position_publisher.launch.py",
            ],
        ),
    ],
    install_requires=["setuptools"],
    zip_safe=True,
    maintainer="syh",
    maintainer_email="syh@example.com",
    description="Validate, buffer, filter, and rate-limit vision target predictions.",
    license="TODO",
    entry_points={
        "console_scripts": [
            "target_manager_node = target_manager.target_manager_node:main",
            "chassis_position_publisher_node = target_manager.chassis_position_publisher_node:main",
        ],
    },
)
