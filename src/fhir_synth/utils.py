"""Deterministic utilities for ID generation, dates, and random selection."""

from __future__ import annotations

import hashlib
import random
import uuid
from datetime import datetime, timedelta
from typing import Any, TypeVar

T = TypeVar("T")


class DeterministicRNG:
    """Deterministic random number generator with seed control."""

    def __init__(self, seed: int) -> None:
        """Initialize with a seed."""
        self.seed = seed
        self._rng = random.Random(seed)

    def random(self) -> float:
        """Generate random float [0.0, 1.0)."""
        return self._rng.random()

    def randint(self, a: int, b: int) -> int:
        """Generate random integer in [a, b]."""
        return self._rng.randint(a, b)

    def choice(self, seq: list[T]) -> T:
        """Choose random element from sequence."""
        return self._rng.choice(seq)

    def choices(
        self, population: list[T], weights: list[float] | None = None, k: int = 1
    ) -> list[T]:
        """Choose k elements with optional weights."""
        return self._rng.choices(population, weights=weights, k=k)

    def sample(self, population: list[T], k: int) -> list[T]:
        """Sample k unique elements without replacement."""
        return self._rng.sample(population, k=k)

    def shuffle(self, seq: list[Any]) -> None:
        """Shuffle list in-place."""
        self._rng.shuffle(seq)

    def uniform(self, a: float, b: float) -> float:
        """Generate random float in [a, b]."""
        return self._rng.uniform(a, b)

    def gauss(self, mu: float, sigma: float) -> float:
        """Generate normally distributed random number."""
        return self._rng.gauss(mu, sigma)

    def fork(self, namespace: str) -> DeterministicRNG:
        """Create a child RNG with deterministic derived seed."""
        # Use hash to create deterministic but different seed
        hash_input = f"{self.seed}:{namespace}"
        hash_digest = hashlib.sha256(hash_input.encode()).digest()
        new_seed = int.from_bytes(hash_digest[:4], byteorder="big")
        return DeterministicRNG(new_seed)


class IDGenerator:
    """Deterministic ID generator."""

    def __init__(self, rng: DeterministicRNG, namespace: str = "") -> None:
        """Initialize with RNG and optional namespace."""
        self.rng = rng
        self.namespace = namespace
        self._counters: dict[str, int] = {}

    def uuid(self, prefix: str = "") -> str:
        """Generate deterministic UUID."""
        # Use RNG state to create deterministic UUID
        random_bytes = bytes([self.rng.randint(0, 255) for _ in range(16)])
        uid = uuid.UUID(bytes=random_bytes, version=4)
        return f"{prefix}{uid}" if prefix else str(uid)

    def sequential(self, resource_type: str, start: int = 1) -> str:
        """Generate sequential ID for resource type."""
        if resource_type not in self._counters:
            self._counters[resource_type] = start
        else:
            self._counters[resource_type] += 1
        return f"{resource_type}-{self._counters[resource_type]}"

    def namespaced(self, resource_type: str, namespace: str) -> str:
        """Generate namespaced ID."""
        key = f"{namespace}:{resource_type}"
        if key not in self._counters:
            self._counters[key] = 1
        else:
            self._counters[key] += 1
        return f"{namespace}-{resource_type}-{self._counters[key]}"


class DateGenerator:
    """Deterministic date/time generator."""

    def __init__(self, rng: DeterministicRNG, start: datetime, end: datetime) -> None:
        """Initialize with RNG and time bounds."""
        self.rng = rng
        self.start = start
        self.end = end
        self.span_seconds = int((end - start).total_seconds())

    def random_datetime(self) -> datetime:
        """Generate random datetime within bounds."""
        offset_seconds = self.rng.randint(0, self.span_seconds)
        return self.start + timedelta(seconds=offset_seconds)

    def random_date(self) -> str:
        """Generate random date string (YYYY-MM-DD)."""
        dt = self.random_datetime()
        return dt.date().isoformat()

    def random_datetime_str(self) -> str:
        """Generate random ISO 8601 datetime string."""
        dt = self.random_datetime()
        return dt.isoformat() + "Z"

    def datetime_between(self, after: datetime, before: datetime) -> datetime:
        """Generate datetime between two specific dates."""
        span = int((before - after).total_seconds())
        if span <= 0:
            return after
        offset = self.rng.randint(0, span)
        return after + timedelta(seconds=offset)

    def date_str_between(self, after: datetime, before: datetime) -> str:
        """Generate date string between two dates."""
        dt = self.datetime_between(after, before)
        return dt.date().isoformat()

    def datetime_str_between(self, after: datetime, before: datetime) -> str:
        """Generate ISO 8601 datetime string between two dates."""
        dt = self.datetime_between(after, before)
        return dt.isoformat() + "Z"

    def add_days(self, dt: datetime, days: int) -> datetime:
        """Add days to datetime."""
        return dt + timedelta(days=days)

    def add_hours(self, dt: datetime, hours: int) -> datetime:
        """Add hours to datetime."""
        return dt + timedelta(hours=hours)


def select_from_distribution(rng: DeterministicRNG, distribution: dict[int, float]) -> int:
    """Select value from a probability distribution."""
    values = list(distribution.keys())
    weights = [distribution[v] for v in values]
    return rng.choices(values, weights=weights, k=1)[0]


def weighted_sample(rng: DeterministicRNG, items: list[T], weights: list[float], k: int) -> list[T]:
    """Sample k items with weights (with replacement if k > len(items))."""
    if k <= len(items):
        # Without replacement using weighted selection
        # Convert to cumulative selection
        selected: list[T] = []
        remaining = list(items)
        remaining_weights = list(weights)

        for _ in range(k):
            chosen = rng.choices(remaining, weights=remaining_weights, k=1)[0]
            idx = remaining.index(chosen)
            selected.append(chosen)
            remaining.pop(idx)
            remaining_weights.pop(idx)

        return selected
    else:
        # With replacement
        return rng.choices(items, weights=weights, k=k)
