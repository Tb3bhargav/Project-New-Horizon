"""
RAM-only Session Context Cache for Project New Horizon.
Maintains up to 5 recent question-and-answer pairs in memory for conversation context.
"""

from typing import List, Dict

class ContextCache:
    """
    In-memory FIFO cache for session Q&A context.
    Strictly RAM-only: cleared when a new session starts and never persisted to disk.
    """
    def __init__(self, capacity: int = 5):
        self.capacity = capacity
        self._history: List[Dict[str, str]] = []

    def add(self, question: str, answer: str) -> None:
        """
        Add a completed Q&A pair to the session cache.
        Enforces FIFO eviction if capacity is exceeded.
        """
        if not question or not answer:
            return

        self._history.append({
            "question": question.strip(),
            "answer": answer.strip()
        })

        # Evict oldest entry if exceeding capacity
        while len(self._history) > self.capacity:
            self._history.pop(0)

    def get_context_messages(self) -> List[Dict[str, str]]:
        """
        Return history formatted as OpenAI/Groq chat message list:
        [
            {"role": "user", "content": q1},
            {"role": "assistant", "content": a1},
            ...
        ]
        """
        messages = []
        for pair in self._history:
            messages.append({"role": "user", "content": pair["question"]})
            messages.append({"role": "assistant", "content": pair["answer"]})
        return messages

    def get_raw_history(self) -> List[Dict[str, str]]:
        """Return raw list of Q&A dictionaries."""
        return list(self._history)

    def clear(self) -> None:
        """Clear all session memory."""
        self._history.clear()

    def __len__(self) -> int:
        return len(self._history)
