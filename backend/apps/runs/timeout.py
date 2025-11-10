"""
Timeout handling for runs.
"""
from __future__ import annotations

import signal
import threading
from contextlib import contextmanager
from typing import Any, Callable, Generator

from django.utils import timezone


class TimeoutError(Exception):
    """Raised when a run exceeds its timeout."""

    pass


def _is_main_thread() -> bool:
    """Check if we're in the main thread."""
    return threading.current_thread() is threading.main_thread()


@contextmanager
def timeout_context(seconds: int) -> Generator[None, None, None]:
    """
    Context manager for timeout handling.

    Uses signal.SIGALRM in main thread, threading.Timer otherwise.
    This is necessary because signals only work in the main thread.

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

    if _is_main_thread():
        # Use signal-based timeout in main thread
        def timeout_handler(signum: int, frame: Any) -> None:
            """Handle timeout signal."""
            raise TimeoutError(f"Operation timed out after {seconds} seconds")

        old_handler = signal.signal(signal.SIGALRM, timeout_handler)
        signal.alarm(seconds)

        try:
            yield
        finally:
            signal.alarm(0)
            signal.signal(signal.SIGALRM, old_handler)
    else:
        # Use threading-based timeout in worker threads
        timeout_occurred = threading.Event()

        def timeout_handler() -> None:
            """Handle timeout in thread."""
            timeout_occurred.set()

        timer = threading.Timer(seconds, timeout_handler)
        timer.start()

        try:
            yield
            if timeout_occurred.is_set():
                raise TimeoutError(f"Operation timed out after {seconds} seconds")
        finally:
            timer.cancel()


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

