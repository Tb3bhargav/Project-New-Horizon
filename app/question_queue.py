"""
Thread-safe FIFO Question Queue for Project New Horizon.
Queues incoming questions received while an answer is currently streaming.
"""

import queue
from typing import Optional

class QuestionQueue:
    """
    FIFO queue wrapper for managing back-to-back questions.
    """
    def __init__(self):
        self._queue: queue.Queue = queue.Queue()

    def enqueue(self, question: str) -> None:
        """Add a question to the queue."""
        if question and question.strip():
            self._queue.put(question.strip())

    def dequeue(self) -> Optional[str]:
        """Get the next question from the queue, or None if empty."""
        try:
            return self._queue.get_nowait()
        except queue.Empty:
            return None

    def is_empty(self) -> bool:
        """Return True if queue is empty."""
        return self._queue.empty()

    def size(self) -> int:
        """Return number of queued questions."""
        return self._queue.qsize()

    def clear(self) -> None:
        """Clear all queued questions."""
        with self._queue.mutex:
            self._queue.queue.clear()
