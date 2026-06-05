from setuptools import find_packages, setup


setup(
    package_dir={"": "src"},
    packages=find_packages(where="src"),
    package_data={
        "cs_demo_downloader": [
            "bin/*.exe",
            "_vendor/cs_demo_pwa_signer/manifest.json",
            "_vendor/cs_demo_pwa_signer/*/*.so",
            "_vendor/cs_demo_pwa_signer/*/*.pyd",
            "_vendor/cs_demo_pwa_signer/*/*.dylib",
        ]
    },
    include_package_data=True,
)
