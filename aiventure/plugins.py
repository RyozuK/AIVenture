"""Plugin system — discovery and registry for extensions.

Plugins are discovered via setuptools entry_points under the ``aiventure.plugins``
group.  Each entry point should resolve to a callable that accepts a
:class:`~aiventure.controller.session.GameSession` and returns ``None``.

Example ``pyproject.toml``::

    [project.entry-points."aiventure.plugins"]
    my_mod = "my_mod.plugin:register"

The callable is invoked once at startup and can:

* Register custom action handlers via ``session.router.register(...)``
* Add custom tool schemas to ``session.llm_service``
* Register custom persistence providers
"""

from __future__ import annotations

import logging
from importlib.metadata import entry_points
from typing import TYPE_CHECKING

logger = logging.getLogger("aiventure.plugins")

if TYPE_CHECKING:
    from aiventure.controller.session import GameSession


GROUP = "aiventure.plugins"


def discover_plugins() -> list:
    """Find and return all registered plugin callables."""
    plugins = []
    try:
        for ep in entry_points(group=GROUP):
            try:
                plugin = ep.load()
                plugins.append(plugin)
                logger.info("Discovered plugin: %s (%s)", ep.name, ep.value)
            except Exception:
                logger.exception("Failed to load plugin entry point '%s'", ep.name)
    except Exception:
        logger.exception("Plugin discovery failed (group=%s)", GROUP)
    return plugins


def initialize_plugins(session: "GameSession") -> None:
    """Call every discovered plugin with the active session."""
    for plugin in discover_plugins():
        try:
            plugin(session)
        except Exception:
            logger.exception("Plugin initialization failed")