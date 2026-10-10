"""Probe the active display session without assuming a compositor or requesting root."""

from __future__ import annotations

import os
import shutil
from dataclasses import dataclass
from typing import Mapping

ALLOWED_BINARIES = {
    "xdotool": ("/usr/bin/xdotool",),
    "wmctrl": ("/usr/bin/wmctrl",),
    "grim": ("/usr/bin/grim",),
    "gnome-screenshot": ("/usr/bin/gnome-screenshot",),
    "xclip": ("/usr/bin/xclip",),
    "wl-copy": ("/usr/bin/wl-copy",),
    "wl-paste": ("/usr/bin/wl-paste",),
    "firefox": ("/usr/bin/firefox",),
    "chromium": ("/usr/bin/chromium", "/usr/bin/chromium-browser"),
}


@dataclass(frozen=True)
class DesktopCapabilities:
    session_type: str
    display: str | None
    wayland_display: str | None
    compositor: str | None
    pointer_keyboard: bool
    window_management: bool
    screenshots: bool
    clipboard: bool
    browser: bool
    tiling: bool
    blockers: tuple[str, ...]
    binaries: dict[str, str]

    def as_dict(self) -> dict:
        return {
            "session_type": self.session_type,
            "display": self.display,
            "wayland_display": self.wayland_display,
            "compositor": self.compositor,
            "pointer_keyboard": self.pointer_keyboard,
            "window_management": self.window_management,
            "screenshots": self.screenshots,
            "clipboard": self.clipboard,
            "browser": self.browser,
            "tiling": self.tiling,
            "blockers": list(self.blockers),
            "binaries": dict(self.binaries),
        }


def _first_executable(candidates: tuple[str, ...], *, which=shutil.which) -> str | None:
    for path in candidates:
        name = os.path.basename(path)
        found = which(name)
        if found == path and os.path.isfile(path) and os.access(path, os.X_OK):
            return path
        if os.path.isfile(path) and os.access(path, os.X_OK):
            return path
    return None


def detect_desktop_capabilities(environ: Mapping[str, str] | None = None, *, which=shutil.which) -> DesktopCapabilities:
    env = environ if environ is not None else os.environ
    display = env.get("DISPLAY") or None
    wayland = env.get("WAYLAND_DISPLAY") or None
    session = (env.get("XDG_SESSION_TYPE") or "").strip().lower()
    desktop = (env.get("XDG_CURRENT_DESKTOP") or env.get("DESKTOP_SESSION") or "").strip() or None
    if session not in {"x11", "wayland"}:
        if wayland:
            session = "wayland"
        elif display:
            session = "x11"
        else:
            session = "unsupported"
    binaries: dict[str, str] = {}
    for name, candidates in ALLOWED_BINARIES.items():
        found = _first_executable(candidates, which=which)
        if found:
            binaries[name] = found
    blockers: list[str] = []
    if session == "unsupported":
        blockers.append("No active X11 or Wayland display session was detected.")
    pointer = bool(binaries.get("xdotool")) if session == "x11" else False
    windows = bool(binaries.get("wmctrl") or binaries.get("xdotool")) if session == "x11" else False
    if session == "wayland":
        blockers.append("Wayland pointer and window management require a compositor-specific interface that is not bound in this adapter.")
        if not binaries.get("grim"):
            blockers.append("Wayland screenshot tool grim is unavailable.")
    screenshots = bool(binaries.get("gnome-screenshot") or binaries.get("grim") or binaries.get("xdotool"))
    clipboard = bool(binaries.get("xclip") if session == "x11" else binaries.get("wl-copy"))
    browser = bool(binaries.get("firefox") or binaries.get("chromium"))
    tiling = windows and session == "x11"
    if not pointer and session == "x11":
        blockers.append("xdotool is unavailable; pointer and keyboard actions cannot run.")
    if not browser:
        blockers.append("No allowlisted browser executable was found.")
    return DesktopCapabilities(
        session_type=session, display=display, wayland_display=wayland, compositor=desktop,
        pointer_keyboard=pointer, window_management=windows, screenshots=screenshots,
        clipboard=clipboard, browser=browser, tiling=tiling, blockers=tuple(blockers), binaries=binaries,
    )
