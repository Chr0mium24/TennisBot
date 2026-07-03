from setuptools import find_packages, setup


package_name = "tennisbot_headless_vision"


setup(
    name=package_name,
    version="0.1.0",
    packages=find_packages(),
    data_files=[
        ("share/ament_index/resource_index/packages", ["resource/" + package_name]),
        ("share/" + package_name, ["package.xml"]),
        ("share/" + package_name + "/config", ["config/headless_vision.yaml"]),
        ("share/" + package_name + "/launch", ["launch/headless_vision.launch.py"]),
    ],
    install_requires=["setuptools"],
    zip_safe=True,
    maintainer="syh",
    maintainer_email="syh@example.com",
    description="TennisBot vision runtime for stereo target prediction.",
    license="TODO",
    entry_points={
        "console_scripts": [
            "headless_vision_node = tennisbot_headless_vision.headless_vision_node:main",
        ],
    },
)
