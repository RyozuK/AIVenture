"""Natural language input → structured command."""

from __future__ import annotations

import re
from dataclasses import dataclass

from aiventure.model.coords import Direction


@dataclass(frozen=True)
class ParsedCommand:
    verb: str
    target: str = ""
    direction: Direction | None = None
    raw: str = ""
    pronoun: str = ""       # "it", "them" referring to last target
    preposition: str = ""   # "with", "on", etc.

    @property
    def is_direction(self) -> bool:
        return self.direction is not None


# ---------------------------------------------------------------------------
# Synonym map: canonical verb → set of accepted aliases
# ---------------------------------------------------------------------------

_VERB_SYNONYMS: dict[str, set[str]] = {
    "move": {"go", "walk", "run", "head", "move"},
    "look": {"look", "examine", "inspect", "check", "obs", "l"},
    "take": {"take", "get", "grab", "pick up", "pickup"},
    "drop": {"drop", "discard", "dump", "leave"},
    "attack": {"attack", "hit", "kill", "smash", "strike"},
    "search": {"search", "explore", "rummage", "probe"},
    "inventory": {"inventory", "i", "inv", "items"},
    "use": {"use", "drink", "activate"},
    "equip": {"equip", "wear", "don", "put on"},
    "unequip": {"unequip", "remove", "take off", "doff"},
    "talk": {"talk", "speak", "chat", "hail", "greet"},
    "quests": {"quests", "quest"},
    "stats": {"stats", "statistics"},
    "save": {"save"},
    "export": {"export", "export world"},
    "quit": {"quit", "exit", "q"},
}

# Reverse lookup: any synonym → canonical verb
_SYNONYM_TO_VERB: dict[str, str] = {}
for _canonical, _aliases in _VERB_SYNONYMS.items():
    for _alias in _aliases:
        _SYNONYM_TO_VERB[_alias] = _canonical


# ---------------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------------

def parse_input(text: str, last_target: str = "") -> ParsedCommand:
    """Tokenize a natural-language command into a structured ParsedCommand.

    Args:
        text: The raw command string.
        last_target: The name of the last entity/item the player referenced.
                     Used for pronoun resolution ("it", "them").

    Examples::

        >>> parse_input("north")
        ParsedCommand(verb="move", direction=NORTH, ...)

        >>> parse_input("take the rusty sword")
        ParsedCommand(verb="take", target="the rusty sword", ...)

        >>> parse_input("attack it")  # last_target="goblin"
        ParsedCommand(verb="attack", target="goblin", pronoun="it", ...)
    """
    raw = text.strip()
    if not raw:
        return ParsedCommand(verb="look", raw=raw)

    lower = raw.lower()

    # Direct direction movement: "north", "go north", "walk south"
    for direction in Direction:
        pattern = rf"^(?:go|walk|run|head|move)?\s*{re.escape(direction.value)}\s*$"
        if re.match(pattern, lower):
            return ParsedCommand(
                verb="move",
                direction=direction,
                raw=raw,
            )

    # "look at <target>" / "examine <target>"
    look_match = re.match(
        r"^(?:look|examine|inspect|check)\s+(?:at\s+)?(.+)$",
        lower,
    )
    if look_match:
        target_text = look_match.group(1).strip()
        resolved, pronoun = _resolve_pronoun(target_text, last_target)
        return ParsedCommand(
            verb="look",
            target=resolved,
            pronoun=pronoun,
            raw=raw,
        )

    # "look" (no target) — exact match for single-letter shortcuts
    if lower in ("look", "l"):
        return ParsedCommand(verb="look", raw=raw)

    # Split into verb phrase + target
    words = lower.split(maxsplit=1)
    if not words:
        return ParsedCommand(verb="unknown", raw=raw)

    verb_candidate = words[0]
    target = words[1].strip() if len(words) > 1 else ""

    # Single-letter shortcuts ("i", "l", "q") only match when they are the
    # *entire* input, not when they are a word in a sentence.
    single_letter_shortcuts = {"i", "l", "q"}
    if verb_candidate in single_letter_shortcuts and target:
        # e.g. "i have a question" — not a command
        return ParsedCommand(verb="unknown", target=raw, raw=raw)

    # Try matching the first word(s) against our synonym map

    # Handle two-word verbs like "pick up"
    if verb_candidate not in _SYNONYM_TO_VERB and target:
        two_word = f"{verb_candidate} {target.split()[0]}" if target.split() else ""
        if two_word in _SYNONYM_TO_VERB:
            verb = _SYNONYM_TO_VERB[two_word]
            # Extract real target after the two-word verb
            parts = lower.split(None, 2)
            target = parts[2].strip() if len(parts) > 2 else ""
        else:
            return ParsedCommand(verb="unknown", target=raw, raw=raw)
    elif verb_candidate in _SYNONYM_TO_VERB:
        verb = _SYNONYM_TO_VERB[verb_candidate]
    else:
        return ParsedCommand(verb="unknown", target=raw, raw=raw)

    # Resolve pronouns in target
    resolved_target, pronoun = _resolve_pronoun(target, last_target)

    # Extract preposition ("attack goblin with sword")
    prep, after_prep = _extract_preposition(resolved_target)

    return ParsedCommand(
        verb=verb,
        target=resolved_target if not prep else after_prep,
        direction=None,
        raw=raw,
        pronoun=pronoun,
        preposition=prep,
    )


def _resolve_pronoun(target: str, last_target: str) -> tuple[str, str]:
    """Resolve 'it', 'them', 'that thing' to the last mentioned target."""
    pronouns = {"it", "them", "that thing", "that", "it there"}
    if target.lower().strip() in pronouns and last_target:
        return last_target, target.lower().strip()
    return target, ""


def _extract_preposition(target: str) -> tuple[str, str]:
    """Extract 'with <weapon>' or 'on <target>' suffix from target.

    Returns (preposition, target_without_suffix).
    """
    for prep in ("with", "on", "against", "upon"):
        parts = target.split(f" {prep} ", 1)
        if len(parts) == 2:
            return prep, parts[0]
    return "", target