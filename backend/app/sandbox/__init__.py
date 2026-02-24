"""Sandbox module for isolated browser automation environments.

This module provides sandbox implementations for running browser_use
in isolated environments, either via Docker containers or Daytona
cloud sandboxes.

Sandboxes provide:
- Isolated execution environment
- VNC streaming for browser visibility
- Browser API access for automation
- Resource limits and timeouts
"""

from app.sandbox.client import SandboxClient
from app.sandbox.manager import SandboxManager, get_sandbox_manager

__all__ = [
    "SandboxClient",
    "SandboxManager",
    "get_sandbox_manager",
]
