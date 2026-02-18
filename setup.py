"""Setup configuration for myapp"""

from setuptools import setup, find_packages

setup(
    name="ado-pr-kpi-generator",
    version="0.1.0",
    description=(
        "CLI tool for Azure DevOps pull request KPIs: first-response dwell "
        "time and completion time."
    ),
    author="ADO PR KPI Generator Contributors",
    author_email="",
    python_requires=">=3.7",
    package_dir={"": "src"},
    packages=find_packages(where="src"),
    install_requires=[
        "requests>=2.28.0",
    ],
    extras_require={
        "dev": [
            "pytest>=7.0",
            "black>=22.0",
            "flake8>=4.0",
            "mypy>=0.950",
        ],
    },
    entry_points={
        "console_scripts": [
            "ado-pr-kpi-generator=myapp.main:main",
        ],
    },
)
