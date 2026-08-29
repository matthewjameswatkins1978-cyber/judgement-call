from typing import Callable, Iterable, TypeVar

T = TypeVar("T")
R = TypeVar("R")


def process_items(items: Iterable[T], worker: Callable[[T], R]) -> list[R]:
    """Process items sequentially using the worker function, preserving input order."""
    results = []
    for item in items:
        results.append(worker(item))
    return results
