"""Console (terminal) client — stdin/stdout game loop."""

from __future__ import annotations

from .base import Client
from .protocol import CommandResult


class ConsoleClient(Client):
    """Simple terminal client that reads from stdin and writes to stdout.

    Uses a strictly synchronous display pattern: results are printed directly
    when received, and the prompt is only shown after the result is fully
    displayed. This avoids the event-loop blocking issues that arise from
    using ``input()`` alongside a background async display task.
    """

    def __init__(self, prompt: str = ":> ") -> None:
        self._prompt = prompt

    async def send_result(self, result: CommandResult) -> None:
        """Print the result immediately. No queue or background task needed."""
        if result.narrative:
            print(result.narrative)
            print()  # blank line after narrative

    async def get_input(self) -> str | None:
        """Read a line from stdin.  Returns None on EOF/quit."""
        try:
            line = input(self._prompt)
            return line.strip()
        except (EOFError, KeyboardInterrupt):
            return None

    async def start(self) -> None:
        """No background tasks needed for the synchronous console client."""
        pass

    async def stop(self) -> None:
        """No background tasks to stop."""
        pass