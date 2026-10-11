"""Local desktop operator: capability detection, workspace, and cancellable actions."""

from .capabilities import detect_desktop_capabilities
from .operator import DesktopOperatorService

__all__ = ["DesktopOperatorService", "detect_desktop_capabilities"]
