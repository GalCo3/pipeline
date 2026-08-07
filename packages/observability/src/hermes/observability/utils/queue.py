from typing import Any

from hermes.observability.constants import QUEUE_DROP_THRESHOLD


def enforce_queue_drop_mode(bp: Any) -> None:
    """
    Enforces a memory-safe drop-mode when the BatchProcessor queue size
    reaches the drop threshold of its max capacity. Discards the oldest element to prevent OOM.
    """
    try:
        if len(bp._queue) >= QUEUE_DROP_THRESHOLD * bp._max_queue_size:
            try:
                bp._queue.pop()  # Discard oldest element from the right
                if hasattr(bp, "_metrics") and hasattr(bp._metrics, "drop_items"):
                    bp._metrics.drop_items(1)
            except IndexError:
                pass
    except Exception:
        pass
