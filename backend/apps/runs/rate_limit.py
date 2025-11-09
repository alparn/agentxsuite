"""
Rate limiting and concurrency control for runs.
"""
from __future__ import annotations

import time
from collections import defaultdict
from threading import Lock

from django.core.cache import cache
from django.utils import timezone

from apps.agents.models import Agent
from apps.runs.models import Run


class RateLimiter:
    """Rate limiter for agent runs."""

    def __init__(self) -> None:
        """Initialize rate limiter with thread-safe locks."""
        self._locks: dict[str, Lock] = defaultdict(Lock)
        self._lock = Lock()

    def _get_lock(self, key: str) -> Lock:
        """Get or create lock for a key."""
        with self._lock:
            if key not in self._locks:
                self._locks[key] = Lock()
            return self._locks[key]

    def check_rate_limit(
        self,
        agent: Agent,
        max_runs_per_minute: int = 60,
        max_concurrent_runs: int = 5,
    ) -> tuple[bool, str | None]:
        """
        Check if agent can start a new run based on rate limits.

        Args:
            agent: Agent instance
            max_runs_per_minute: Maximum runs per minute per agent
            max_concurrent_runs: Maximum concurrent runs per agent

        Returns:
            Tuple of (allowed: bool, reason: str | None)
        """
        agent_key = f"rate_limit:{agent.id}"

        # Check concurrent runs
        concurrent_count = Run.objects.filter(
            agent=agent,
            status__in=["pending", "running"],
        ).count()

        if concurrent_count >= max_concurrent_runs:
            return False, f"Maximum concurrent runs ({max_concurrent_runs}) exceeded"

        # Check rate limit using cache
        cache_key = f"{agent_key}:minute"
        current_minute = int(time.time() / 60)
        minute_key = f"{cache_key}:{current_minute}"

        run_count = cache.get(minute_key, 0)
        if run_count >= max_runs_per_minute:
            return False, f"Rate limit exceeded: {max_runs_per_minute} runs/minute"

        # Increment counter
        cache.set(minute_key, run_count + 1, timeout=120)  # 2 minutes TTL

        return True, None


# Global rate limiter instance
_rate_limiter = RateLimiter()


def check_rate_limit(agent: Agent) -> tuple[bool, str | None]:
    """
    Check rate limit for agent (convenience function).

    Args:
        agent: Agent instance

    Returns:
        Tuple of (allowed: bool, reason: str | None)
    """
    return _rate_limiter.check_rate_limit(agent)

