"""Setup configuration for myapp"""

from setuptools import setup, find_packages

setup(
    name="myapp",
    version="0.1.0",
    description="Azure DevOps PR KPI generator example",
    author="Your Name",
    author_email="your.email@example.com",
    python_requires=">=3.8",
    package_dir={"": "src"},
    packages=find_packages(where="src"),
    install_requires=[
        "requests>=2.31.0",
    ],
    extras_require={
        "dev": [
            "pytest>=7.0",
            "black>=22.0",
            "flake8>=4.0",
            "mypy>=0.950",
        ],
    },
)
