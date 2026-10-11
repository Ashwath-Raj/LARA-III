"""Bounded local desktop notification adapters."""

import subprocess
from pathlib import Path
from typing import Protocol


class NotificationError(RuntimeError):
    def __init__(self, classification: str):
        self.classification = classification
        super().__init__(classification)


class NotificationAdapter(Protocol):
    def notify(self, title: str, message: str) -> None: ...


class FakeNotificationAdapter:
    def __init__(self, *, fail: bool = False):
        self.fail = fail
        self.notifications: list[tuple[str, str]] = []

    def notify(self, title: str, message: str) -> None:
        if self.fail:
            raise NotificationError("notification_failed")
        self.notifications.append((title[:100], message[:500]))


class UbuntuNotificationAdapter:
    def __init__(self, *, timeout_seconds: float = 5.0):
        self.timeout_seconds = timeout_seconds

    def notify(self, title: str, message: str) -> None:
        executable = "/usr/bin/notify-send"
        if not Path(executable).is_file():
            raise NotificationError("notification_unavailable")
        try:
            completed = subprocess.run([executable, title[:100], message[:500]], shell=False,
                                       check=False, capture_output=True, timeout=self.timeout_seconds)
        except subprocess.TimeoutExpired as exc:
            raise NotificationError("notification_failed") from exc
        except OSError as exc:
            raise NotificationError("notification_unavailable") from exc
        if completed.returncode != 0:
            raise NotificationError("notification_unavailable")

