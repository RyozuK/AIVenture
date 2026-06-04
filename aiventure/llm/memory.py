"""Context memory management — token budget and sliding window."""

from __future__ import annotations

import logging

logger = logging.getLogger("aiventure.llm.memory")


class MemoryManager:
    """Manages the LLM context budget.

    Keeps a sliding window of recent turns, summarizes older turns,
    and prunes stale ambient details to stay within a token budget.
    """

    def __init__(
        self,
        max_turns: int = 20,
        max_context_chars: int = 8000,
    ) -> None:
        self._max_turns = max_turns
        self._max_context_chars = max_context_chars
        self._turns: list[str] = []
        self._summary: str = ""

    def add_turn(self, turn_text: str) -> None:
        """Record a turn entry."""
        self._turns.append(turn_text)
        self._prune_if_needed()

    def get_recent_turns(self) -> list[str]:
        """Return the last N turns without summarization."""
        return self._turns[-self._max_turns:]

    def get_context_parts(self) -> tuple[str | None, list[str]]:
        """Return (summary_of_old_turns, recent_turns)."""
        return (
            self._summary if self._summary else None,
            self._turns[-self._max_turns:],
        )

    def estimate_token_count(self, text: str) -> int:
        """Rough token estimate (~4 chars per token)."""
        return len(text) // 4 + 1

    def _prune_if_needed(self) -> None:
        """Summarize and prune if the context is getting too large."""
        total = self._estimate_total_chars()
        if total > self._max_context_chars and len(self._turns) > 5:
            # Summarize the oldest half
            mid = len(self._turns) // 2
            old_text = "\n".join(self._turns[:mid])
            self._summary = f"[Summarized earlier gameplay ({mid} turns)]: " + old_text[:500] + "..."
            self._turns = self._turns[mid:]
            logger.debug("Context pruned: %d old turns summarized", mid)

    def _estimate_total_chars(self) -> int:
        summary_chars = len(self._summary) if self._summary else 0
        turns_chars = sum(len(t) for t in self._turns)
        return summary_chars + turns_chars

    def clear(self) -> None:
        self._turns.clear()
        self._summary = ""