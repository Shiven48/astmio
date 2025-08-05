from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .manager import PluginManager

log = logging.getLogger(__name__)


class BasePlugin:
    """
    Base class for all plugins. It defines the interface that all plugins must implement.
    This is the core "contract" of the plugin system.
    """

    name: str = "BasePlugin"
    version: str = "1.0.0"
    description: str = "Base plugin class"

    def __init__(self, **kwargs):
        self.config = kwargs
        self.manager: PluginManager | None = None

    def install(self, manager: PluginManager):
        self.manager = manager
        log.info(f"Installing plugin: {self.name}")

    def uninstall(self, manager: PluginManager):
        log.info(f"Uninstalling plugin: {self.name}")
        self.manager = None
