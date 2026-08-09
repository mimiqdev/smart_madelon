"""Data update coordinator for Madelon Ventilation."""

from __future__ import annotations

# pyright: reportMissingImports=false
import logging
from datetime import timedelta

from homeassistant.config_entries import (
    ConfigEntry,  # pyright: ignore[reportMissingImports]
)
from homeassistant.core import HomeAssistant  # pyright: ignore[reportMissingImports]
from homeassistant.helpers.update_coordinator import (  # pyright: ignore[reportMissingImports]
    DataUpdateCoordinator,
    UpdateFailed,
)

from .const import DOMAIN
from .fresh_air_controller import FreshAirSystem

_LOGGER = logging.getLogger(__name__)


class MadelonVentilationCoordinator(DataUpdateCoordinator[FreshAirSystem]):
    """Coordinate a single batch register read for all entities."""

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        system: FreshAirSystem,
        update_interval: timedelta,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=DOMAIN,
            update_interval=update_interval,
        )
        self.system = system

    async def _async_update_data(self) -> FreshAirSystem:
        """Read the complete register snapshot exactly once."""
        success = await self.hass.async_add_executor_job(
            self.system.refresh_registers, True
        )
        if not success:
            raise UpdateFailed("Unable to read ventilation registers")
        return self.system
