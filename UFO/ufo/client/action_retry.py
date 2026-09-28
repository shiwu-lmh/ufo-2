"""Small async retry primitive used by desktop action execution."""

from typing import Awaitable, Callable, Optional, TypeVar


T = TypeVar("T")


async def execute_with_retries(
    operation: Callable[[], Awaitable[T]],
    *,
    max_retries: int,
    is_success: Callable[[T], bool],
    before_retry: Optional[Callable[[int], Awaitable[None]]] = None,
) -> T:
    """Run an operation once, then retry it at most ``max_retries`` times.

    ``before_retry`` receives the one-based retry number and is intended for
    refreshing UI state before the next attempt. The helper deliberately does
    not sleep or swallow exceptions; callers decide how to classify failures.
    """

    retries = max(0, int(max_retries))
    result: Optional[T] = None

    for attempt in range(retries + 1):
        result = await operation()
        if is_success(result):
            return result

        if attempt < retries and before_retry is not None:
            await before_retry(attempt + 1)

    return result  # type: ignore[return-value]
