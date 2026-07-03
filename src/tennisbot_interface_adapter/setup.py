from setuptools import find_packages, setup


package_name = "tennisbot_interface_adapter"


setup(
    name=package_name,
    version="0.1.0",
    packages=find_packages(),
    data_files=[
        ("share/ament_index/resource_index/packages", ["resource/" + package_name]),
        ("share/" + package_name, ["package.xml"]),
        ("share/" + package_name + "/config", ["config/interface_adapter.yaml"]),
        ("share/" + package_name + "/launch", ["launch/interface_adapter.launch.py"]),
    ],
    install_requires=["setuptools"],
    zip_safe=True,
    maintainer="syh",
    maintainer_email="syh@example.com",
    description="Adapt TennisBot vision ROS topics to the external target interface.",
    license="TODO",
    entry_points={
        "console_scripts": [
            "vision_interface_adapter_node = tennisbot_interface_adapter.vision_interface_adapter_node:main",
        ],
    },
)
