"""Tests for main module"""

import sys
from pathlib import Path

# Add src directory to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from myapp.main import hello_world


def test_hello_world_default():
    """Test hello_world with default name"""
    result = hello_world()
    assert result == "Hello, World!"


def test_hello_world_custom():
    """Test hello_world with custom name"""
    result = hello_world("Alice")
    assert result == "Hello, Alice!"
