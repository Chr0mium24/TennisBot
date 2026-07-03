from setuptools import find_packages, setup


package_name = "tennisbot_vision_runtime"


setup(
    name=package_name,
    version="0.1.0",
    packages=find_packages(),
    data_files=[
        ("share/ament_index/resource_index/packages", ["resource/" + package_name]),
        ("share/" + package_name, ["package.xml"]),
        ("share/" + package_name + "/config", ["config/vision_runtime.yaml"]),
        ("share/" + package_name + "/launch", ["launch/vision_runtime.launch.py"]),
    ],
    install_requires=["setuptools"],
    zip_safe=True,
    maintainer="syh",
    maintainer_email="syh@example.com",
    description="TennisBot vision runtime for stereo target prediction.",
    license="TODO",
    entry_points={
        "console_scripts": [
            "vision_runtime_node = tennisbot_vision_runtime.vision_runtime_node:main",
        ],
    },
)
