from setuptools import find_packages, setup


setup(
    package_dir={"": "src"},
    packages=find_packages(where="src"),
    package_data={"cs_demo_downloader": ["bin/*.exe"]},
    include_package_data=True,
)
