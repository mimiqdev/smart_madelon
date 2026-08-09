"""Button platform for Madelon Ventilation."""

from __future__ import annotations

# pyright: reportMissingImports=false

import logging

from homeassistant.components.button import (  # pyright: ignore[reportMissingImports]
    ButtonEntity,
)
from homeassistant.config_entries import (
    ConfigEntry,  # pyright: ignore[reportMissingImports]
)
from homeassistant.core import HomeAssistant  # pyright: ignore[reportMissingImports]
from homeassistant.helpers.device_registry import (  # pyright: ignore[reportMissingImports]
    DeviceInfo,
)
from homeassistant.helpers.entity_platform import (  # pyright: ignore[reportMissingImports]
    AddEntitiesCallback,
)
from homeassistant.helpers.update_coordinator import (  # pyright: ignore[reportMissingImports]
    CoordinatorEntity,
)

from .const import DEVICE_MANUFACTURER, DEVICE_MODEL, DEVICE_SW_VERSION, DOMAIN
from .coordinator import MadelonVentilationCoordinator  # pyright: ignore[reportMissingImports]
from .fresh_air_controller import FreshAirSystem

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Fresh Air System buttons."""
    coordinator = hass.data[DOMAIN][config_entry.entry_id]["coordinator"]
    async_add_entities([FilterResetButton(coordinator)])


class FilterResetButton(CoordinatorEntity[MadelonVentilationCoordinator], ButtonEntity):
    """Button to reset filter usage time."""

    def __init__(self, coordinator: MadelonVentilationCoordinator) -> None:
        """Initialize the filter reset button."""
        super().__init__(coordinator)
        self._system: FreshAirSystem = coordinator.system
        self._attr_has_entity_name = True
        self._attr_name = "Reset Filter Usage"
        self._attr_unique_id = f"{DOMAIN}_{self._system.unique_identifier}_filter_reset"
        self._attr_icon = "mdi:filter-remove"

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information about this entity."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._system.unique_identifier)},
            name="Fresh Air System",
            manufacturer=DEVICE_MANUFACTURER,
            model=DEVICE_MODEL,
            sw_version=DEVICE_SW_VERSION,
        )

    async def async_press(self) -> None:
        """Handle the button press."""
        result = await self.hass.async_add_executor_job(
            self._system.reset_filter_usage_time
        )
        if result:
            _LOGGER.info("Filter usage time reset successfully")
            await self.coordinator.async_request_refresh()
        else:
            _LOGGER.error("Failed to reset filter usage time")
