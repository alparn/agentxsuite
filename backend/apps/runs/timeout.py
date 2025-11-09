"""
Timeout handling for runs.
"""
from __future__ import annotations

import signal
from contextlib import contextmanager
from typing import Any, Callable, Generator

from django.utils import timezone


class TimeoutError(Exception):
    """Raised when a run exceeds its timeout."""

    pass


@contextmanager
def timeout_context(seconds: int) -> Generator[None, None, None]:
    """
    Context manager for timeout handling.

    Args:
        seconds: Timeout in seconds

    Yields:
        None

    Raises:
        TimeoutError: If operation exceeds timeout
    """
    if seconds <= 0:
        yield
        return

    def timeout_handler(signum: int, frame: Any) -> None:
        """Handle timeout signal."""
        raise TimeoutError(f"Operation timed out after {seconds} seconds")

    # Set up signal handler
    old_handler = signal.signal(signal.SIGALRM, timeout_handler)
    signal.alarm(seconds)

    try:
        yield
    finally:
        # Restore old handler and cancel alarm
        signal.alarm(0)
        signal.signal(signal.SIGALRM, old_handler)


def execute_with_timeout(
    func: Callable[[], Any],
    timeout_seconds: int = 30,
    default_result: Any = None,
) -> Any:
    """
    Execute a function with timeout protection.

    Args:
        func: Function to execute
        timeout_seconds: Maximum execution time in seconds
        default_result: Value to return on timeout

    Returns:
        Function result or default_result on timeout
    """
    try:
        with timeout_context(timeout_seconds):
            return func()
    except TimeoutError:
        return default_result

