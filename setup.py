#!/usr/bin/env python
from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="flatback",
    version="1.0",
    packages=find_packages(),
    entry_points={
        "console_scripts": [
            "flatback = flatback.__main__:main",
        ],
    },
    url="https://github.com/jfhack/flatback",
    install_requires=[
        "pyyaml",
    ],
    long_description=long_description,
    long_description_content_type="text/markdown",
)
