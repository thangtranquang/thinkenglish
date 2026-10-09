"""Run callables in threads released together by a barrier."""
from __future__ import annotations

import threading
from collections.abc import Callable


def run_together(fns: list[Callable[[], object]]) -> list[object]:
    barrier = threading.Barrier(len(fns))
    results: list[object] = [None] * len(fns)

    def worker(i: int, fn: Callable[[], object]) -> None:
        barrier.wait(timeout=10)
        try:
            results[i] = fn()
        except BaseException as exc:  # surfaced to the test
            results[i] = exc

    threads = [threading.Thread(target=worker, args=(i, f)) for i, f in enumerate(fns)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=30)
    for r in results:
        if isinstance(r, BaseException):
            raise r
    return results
