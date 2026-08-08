from __future__ import annotations

import time
from collections import defaultdict, deque
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class LoginAttemptKey:
    client_ip: str
    username: str


class LoginRateLimiter:
    def __init__(self, *, max_attempts: int = 5, window_seconds: float = 900) -> None:
        self._max_attempts = max_attempts
        self._window_seconds = window_seconds
        self._attempts: dict[LoginAttemptKey, deque[float]] = defaultdict(deque)

    def is_blocked(self, key: LoginAttemptKey, *, now: float | None = None) -> bool:
        attempts = self._active_attempts(key, now=now)
        return len(attempts) >= self._max_attempts

    def record_failure(self, key: LoginAttemptKey, *, now: float | None = None) -> None:
        timestamp = time.monotonic() if now is None else now
        attempts = self._active_attempts(key, now=timestamp)
        attempts.append(timestamp)

    def clear(self, key: LoginAttemptKey) -> None:
        self._attempts.pop(key, None)

    def _active_attempts(
        self,
        key: LoginAttemptKey,
        *,
        now: float | None,
    ) -> deque[float]:
        timestamp = time.monotonic() if now is None else now
        attempts = self._attempts[key]
        cutoff = timestamp - self._window_seconds
        while attempts and attempts[0] <= cutoff:
            attempts.popleft()
        if not attempts:
            self._attempts.pop(key, None)
            attempts = self._attempts[key]
        return attempts
