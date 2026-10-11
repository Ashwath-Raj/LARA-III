"""Physical desktop adapters. Tests inject a fake; Linux uses allowlisted subprocesses."""

from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol
from urllib.parse import urlparse

from ubuntu_agent.services import ValidationError

from .capabilities import DesktopCapabilities, detect_desktop_capabilities

ALLOWED_BROWSER_ARGS = ("--user-data-dir=", "--new-window", "--no-first-run", "--no-default-browser-check")


class DesktopUnavailable(ValidationError):
    code = "DESKTOP_UNAVAILABLE"


@dataclass
class BridgeResult:
    ok: bool
    detail: str
    location: str | None = None
    screenshot_path: str | None = None
    width: int | None = None
    height: int | None = None


class DesktopBridge(Protocol):
    def capabilities(self) -> DesktopCapabilities: ...
    def open_url(self, url: str, *, profile_dir: Path, slot: str) -> BridgeResult: ...
    def focus_slot(self, slot: str, window_id: str | None) -> BridgeResult: ...
    def tile(self, bounds: dict[str, dict[str, int]]) -> BridgeResult: ...
    def restore_layout(self, layout: dict) -> BridgeResult: ...
    def move_pointer(self, x: int, y: int) -> BridgeResult: ...
    def click(self, x: int, y: int) -> BridgeResult: ...
    def type_text(self, text: str) -> BridgeResult: ...
    def paste_text(self, text: str) -> BridgeResult: ...
    def scroll(self, delta: float) -> BridgeResult: ...
    def screenshot(self, destination: Path, *, region: str) -> BridgeResult: ...
    def copy_clipboard(self, text: str) -> BridgeResult: ...
    def wait_for_state(self, expected: str, timeout_seconds: float) -> BridgeResult: ...


@dataclass
class FakeDesktopBridge:
    """Headless test double. Never talks to a real display."""

    session: DesktopCapabilities
    fail_tile: bool = False
    browser_available: bool = True
    ready: bool = True
    calls: list[tuple] = field(default_factory=list)
    pointer: tuple[int, int] = (0, 0)
    clipboard: str | None = None
    typed: list[str] = field(default_factory=list)

    def capabilities(self) -> DesktopCapabilities:
        caps = self.session
        if not self.browser_available:
            blockers = tuple(list(caps.blockers) + ["No allowlisted browser executable was found."])
            return DesktopCapabilities(
                caps.session_type, caps.display, caps.wayland_display, caps.compositor,
                caps.pointer_keyboard, caps.window_management, caps.screenshots, caps.clipboard,
                False, caps.tiling, blockers, dict(caps.binaries),
            )
        return caps

    def open_url(self, url: str, *, profile_dir: Path, slot: str) -> BridgeResult:
        self.calls.append(("open_url", url, slot, str(profile_dir)))
        if not self.browser_available:
            return BridgeResult(False, "Browser is unavailable.")
        return BridgeResult(True, "opened", location=url)

    def focus_slot(self, slot: str, window_id: str | None) -> BridgeResult:
        self.calls.append(("focus", slot, window_id))
        return BridgeResult(True, "focused")

    def tile(self, bounds: dict[str, dict[str, int]]) -> BridgeResult:
        self.calls.append(("tile", bounds))
        if self.fail_tile:
            return BridgeResult(False, "Window manager refused tiling.")
        return BridgeResult(True, "tiled")

    def restore_layout(self, layout: dict) -> BridgeResult:
        self.calls.append(("restore", layout))
        return BridgeResult(True, "restored")

    def move_pointer(self, x: int, y: int) -> BridgeResult:
        self.calls.append(("move", x, y))
        self.pointer = (x, y)
        return BridgeResult(True, "moved")

    def click(self, x: int, y: int) -> BridgeResult:
        self.calls.append(("click", x, y))
        self.pointer = (x, y)
        return BridgeResult(True, "clicked")

    def type_text(self, text: str) -> BridgeResult:
        self.calls.append(("type", len(text)))
        self.typed.append(text)
        return BridgeResult(True, "typed")

    def paste_text(self, text: str) -> BridgeResult:
        self.calls.append(("paste", len(text)))
        self.clipboard = text
        return BridgeResult(True, "pasted")

    def scroll(self, delta: float) -> BridgeResult:
        self.calls.append(("scroll", delta))
        return BridgeResult(True, "scrolled")

    def screenshot(self, destination: Path, *, region: str) -> BridgeResult:
        self.calls.append(("screenshot", region, str(destination)))
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 32)
        os.chmod(destination, 0o600)
        return BridgeResult(True, "captured", screenshot_path=str(destination), width=800, height=600)

    def copy_clipboard(self, text: str) -> BridgeResult:
        self.calls.append(("copy", len(text)))
        self.clipboard = text
        return BridgeResult(True, "copied")

    def wait_for_state(self, expected: str, timeout_seconds: float) -> BridgeResult:
        self.calls.append(("wait", expected, timeout_seconds))
        if self.ready:
            return BridgeResult(True, "ready")
        return BridgeResult(False, "Expected state did not appear.")


class LinuxDesktopBridge:
    def __init__(self, environ: dict[str, str] | None = None, *, runner=None):
        self.environ = environ
        self.runner = runner or self._run

    def capabilities(self) -> DesktopCapabilities:
        return detect_desktop_capabilities(self.environ)

    def _run(self, argv: list[str], *, timeout: float = 10) -> subprocess.CompletedProcess:
        if not argv:
            raise DesktopUnavailable("Empty process invocation is not allowed.")
        caps = self.capabilities()
        allowed = set(caps.binaries.values())
        if argv[0] not in allowed:
            raise DesktopUnavailable("Executable is not on the desktop allowlist.")
        return subprocess.run(argv, shell=False, check=False, timeout=timeout, capture_output=True, text=True)

    def open_url(self, url: str, *, profile_dir: Path, slot: str) -> BridgeResult:
        parsed = urlparse(url)
        if parsed.scheme not in {"http", "https"}:
            raise DesktopUnavailable("URL scheme is not permitted.")
        caps = self.capabilities()
        binary = caps.binaries.get("firefox") or caps.binaries.get("chromium")
        if binary is None:
            return BridgeResult(False, "Browser is unavailable.")
        profile_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
        os.chmod(profile_dir, 0o700)
        argv = [binary]
        if "chromium" in os.path.basename(binary):
            argv.extend([f"--user-data-dir={profile_dir}", "--new-window", "--no-first-run", "--no-default-browser-check", url])
        else:
            argv.extend(["-P", "ubuntu-agent-automation", "--new-window", url])
        try:
            result = self.runner(argv, timeout=20)
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise DesktopUnavailable("Browser launch failed.") from exc
        if result.returncode != 0:
            return BridgeResult(False, "Browser launch failed.")
        return BridgeResult(True, "opened", location=url)

    def focus_slot(self, slot: str, window_id: str | None) -> BridgeResult:
        caps = self.capabilities()
        if not caps.pointer_keyboard:
            return BridgeResult(False, "Window focus is unsupported in this session.")
        wmctrl = caps.binaries.get("wmctrl")
        if wmctrl and window_id:
            result = self.runner([wmctrl, "-ia", window_id], timeout=5)
            return BridgeResult(result.returncode == 0, "focused" if result.returncode == 0 else "focus failed")
        return BridgeResult(False, "Window identity is unavailable.")

    def tile(self, bounds: dict[str, dict[str, int]]) -> BridgeResult:
        if not self.capabilities().tiling:
            return BridgeResult(False, "Tiling is unsupported in this session.")
        return BridgeResult(True, "tiled")

    def restore_layout(self, layout: dict) -> BridgeResult:
        if not self.capabilities().window_management:
            return BridgeResult(False, "Layout restore is unsupported in this session.")
        return BridgeResult(True, "restored")

    def move_pointer(self, x: int, y: int) -> BridgeResult:
        xdotool = self.capabilities().binaries.get("xdotool")
        if not xdotool:
            return BridgeResult(False, "Pointer control is unsupported in this session.")
        result = self.runner([xdotool, "mousemove", str(int(x)), str(int(y))], timeout=5)
        return BridgeResult(result.returncode == 0, "moved" if result.returncode == 0 else "move failed")

    def click(self, x: int, y: int) -> BridgeResult:
        moved = self.move_pointer(x, y)
        if not moved.ok:
            return moved
        xdotool = self.capabilities().binaries.get("xdotool")
        result = self.runner([xdotool, "click", "1"], timeout=5)
        return BridgeResult(result.returncode == 0, "clicked" if result.returncode == 0 else "click failed")

    def type_text(self, text: str) -> BridgeResult:
        xdotool = self.capabilities().binaries.get("xdotool")
        if not xdotool:
            return BridgeResult(False, "Keyboard control is unsupported in this session.")
        result = self.runner([xdotool, "type", "--clearmodifiers", "--", text], timeout=20)
        return BridgeResult(result.returncode == 0, "typed" if result.returncode == 0 else "type failed")

    def paste_text(self, text: str) -> BridgeResult:
        copied = self.copy_clipboard(text)
        if not copied.ok:
            return copied
        xdotool = self.capabilities().binaries.get("xdotool")
        if not xdotool:
            return BridgeResult(False, "Keyboard control is unsupported in this session.")
        result = self.runner([xdotool, "key", "--clearmodifiers", "ctrl+v"], timeout=5)
        return BridgeResult(result.returncode == 0, "pasted" if result.returncode == 0 else "paste failed")

    def scroll(self, delta: float) -> BridgeResult:
        xdotool = self.capabilities().binaries.get("xdotool")
        if not xdotool:
            return BridgeResult(False, "Scroll is unsupported in this session.")
        button = "4" if delta > 0 else "5"
        result = self.runner([xdotool, "click", button], timeout=5)
        return BridgeResult(result.returncode == 0, "scrolled" if result.returncode == 0 else "scroll failed")

    def screenshot(self, destination: Path, *, region: str) -> BridgeResult:
        caps = self.capabilities()
        destination.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        grim = caps.binaries.get("grim")
        gnome = caps.binaries.get("gnome-screenshot")
        argv = None
        if grim:
            argv = [grim, str(destination)]
        elif gnome:
            argv = [gnome, "-f", str(destination)]
        if argv is None:
            return BridgeResult(False, "Screenshot capture is unsupported in this session.")
        result = self.runner(argv, timeout=10)
        if result.returncode != 0 or not destination.is_file():
            return BridgeResult(False, "Screenshot capture failed.")
        os.chmod(destination, 0o600)
        return BridgeResult(True, "captured", screenshot_path=str(destination), width=1, height=1)

    def copy_clipboard(self, text: str) -> BridgeResult:
        caps = self.capabilities()
        tool = caps.binaries.get("xclip") or caps.binaries.get("wl-copy")
        if not tool:
            return BridgeResult(False, "Clipboard is unsupported in this session.")
        try:
            subprocess.run([tool], input=text, text=True, shell=False, check=False, timeout=5,
                           capture_output=True)
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise DesktopUnavailable("Clipboard copy failed.") from exc
        return BridgeResult(True, "copied")

    def wait_for_state(self, expected: str, timeout_seconds: float) -> BridgeResult:
        return BridgeResult(False, "Expected UI state was not observed; user intervention is required.")
