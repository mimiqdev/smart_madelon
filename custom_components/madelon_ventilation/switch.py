"""Switch platform for Madelon Ventilation."""

from __future__ import annotations

# pyright: reportMissingImports=false

import logging
from typing import Any

from homeassistant.components.switch import (  # pyright: ignore[reportMissingImports]
    SwitchEntity,
)
from homeassistant.config_entries import (
    ConfigEntry,  # pyright: ignore[reportMissingImports]
)
from homeassistant.core import (  # pyright: ignore[reportMissingImports]
    HomeAssistant,
    callback,
)
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
from .fresh_air_controller import FreshAirSystem, OperationMode

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Madelon Ventilation switches."""
    coordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    async_add_entities(
        [
            MadelonAutoModeSwitch(coordinator),
            MadelonBypassSwitch(coordinator),
        ]
    )


class MadelonSwitchEntity(
    CoordinatorEntity[MadelonVentilationCoordinator], SwitchEntity
):
    """Base class for switches using the shared register snapshot."""

    def __init__(self, coordinator: MadelonVentilationCoordinator) -> None:
        """Initialize the switch."""
        super().__init__(coordinator)
        self._system: FreshAirSystem = coordinator.system
        self._attr_has_entity_name = True
        self._attr_is_on = False
        if coordinator.last_update_success:
            self._update_from_snapshot()

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

    def _update_from_snapshot(self) -> None:
        """Copy state from the latest successful shared snapshot."""
        raise NotImplementedError

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle a shared register snapshot update."""
        if self.coordinator.last_update_success:
            self._update_from_snapshot()
        super()._handle_coordinator_update()

    async def _async_refresh_after_write(self, success: bool) -> None:
        if success:
            await self.coordinator.async_request_refresh()


class MadelonAutoModeSwitch(MadelonSwitchEntity):
    """Representation of a Madelon Ventilation auto/manual mode switch."""

    def __init__(self, coordinator: MadelonVentilationCoordinator) -> None:
        """Initialize the switch."""
        self._attr_name = "Auto Mode"
        self._attr_unique_id = (
            f"{DOMAIN}_{coordinator.system.unique_identifier}_auto_mode"
        )
        super().__init__(coordinator)

    def _update_from_snapshot(self) -> None:
        current_mode = self._system.mode
        if current_mode is not None:
            self._attr_is_on = current_mode == OperationMode.AUTO

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on auto mode."""
        success = await self.hass.async_add_executor_job(
            self._system.set_mode, OperationMode.AUTO
        )
        if not success:
            _LOGGER.error("Failed to set auto mode")
        await self._async_refresh_after_write(success)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off auto mode (switch to manual mode)."""
        success = await self.hass.async_add_executor_job(
            self._system.set_mode, OperationMode.MANUAL
        )
        if not success:
            _LOGGER.error("Failed to set manual mode")
        await self._async_refresh_after_write(success)


class MadelonBypassSwitch(MadelonSwitchEntity):
    """Representation of a Madelon Ventilation bypass switch."""

    def __init__(self, coordinator: MadelonVentilationCoordinator) -> None:
        """Initialize the bypass switch."""
        self._attr_name = "Bypass"
        self._attr_unique_id = f"{DOMAIN}_{coordinator.system.unique_identifier}_bypass"
        super().__init__(coordinator)

    def _update_from_snapshot(self) -> None:
        bypass = self._system.bypass
        if bypass is not None:
            self._attr_is_on = bypass

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the bypass on."""
        success = await self.hass.async_add_executor_job(self._system.set_bypass, True)
        if not success:
            _LOGGER.error("Failed to turn on bypass")
        await self._async_refresh_after_write(success)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the bypass off."""
        success = await self.hass.async_add_executor_job(self._system.set_bypass, False)
        if not success:
            _LOGGER.error("Failed to turn off bypass")
        await self._async_refresh_after_write(success)
