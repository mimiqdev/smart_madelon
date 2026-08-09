"""Fan platform for Madelon Ventilation."""

from __future__ import annotations

# pyright: reportMissingImports=false
import logging
from typing import Any

from homeassistant.components.fan import (  # pyright: ignore[reportMissingImports]
    FanEntity,
    FanEntityFeature,
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
from homeassistant.util.percentage import (  # pyright: ignore[reportMissingImports]
    ordered_list_item_to_percentage,
    percentage_to_ordered_list_item,
)

from .const import DEVICE_MANUFACTURER, DEVICE_MODEL, DEVICE_SW_VERSION, DOMAIN
from .coordinator import (
    MadelonVentilationCoordinator,  # pyright: ignore[reportMissingImports]
)
from .fresh_air_controller import FreshAirSystem

_LOGGER = logging.getLogger(__name__)
ORDERED_NAMED_FAN_SPEEDS = ["low", "medium", "high"]


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Fresh Air System fans."""
    coordinator = hass.data[DOMAIN][config_entry.entry_id]["coordinator"]
    async_add_entities(
        [
            FreshAirFan(coordinator, "supply"),
            FreshAirFan(coordinator, "exhaust"),
        ]
    )


class FreshAirFan(CoordinatorEntity[MadelonVentilationCoordinator], FanEntity):
    """Fresh Air System fan entity."""

    def __init__(
        self, coordinator: MadelonVentilationCoordinator, fan_type: str
    ) -> None:
        """Initialize a fan backed by the shared coordinator snapshot."""
        super().__init__(coordinator)
        self._system: FreshAirSystem = coordinator.system
        self._fan_type = fan_type.lower()
        self._attr_has_entity_name = True
        self._attr_name = f"{fan_type.capitalize()} Fan"
        self._attr_is_on = False
        self._attr_percentage = 0
        self._attr_speed_count = len(ORDERED_NAMED_FAN_SPEEDS)
        self._attr_unique_id = (
            f"{DOMAIN}_{self._fan_type}_fan_{self._system.unique_identifier}"
        )
        self._attr_preset_modes = None
        self._attr_preset_mode = None
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

    @property
    def supported_features(self) -> FanEntityFeature:
        """Flag supported features."""
        return (
            FanEntityFeature.SET_SPEED
            | FanEntityFeature.TURN_ON
            | FanEntityFeature.TURN_OFF
        )

    def _update_from_snapshot(self) -> None:
        """Copy state from the latest successful shared snapshot."""
        power = self._system.power
        speed = (
            self._system.supply_speed
            if self._fan_type == "supply"
            else self._system.exhaust_speed
        )
        if power is None or speed is None:
            return

        self._attr_is_on = power
        if not power:
            self._attr_percentage = 0
            return
        try:
            self._attr_percentage = ordered_list_item_to_percentage(
                ORDERED_NAMED_FAN_SPEEDS, speed
            )
        except ValueError:
            _LOGGER.warning("Invalid %s speed value: %s", self._fan_type, speed)
            self._attr_percentage = 0

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle a shared register snapshot update."""
        if self.coordinator.last_update_success:
            self._update_from_snapshot()
        super()._handle_coordinator_update()

    async def _async_refresh_after_write(self, success: bool) -> None:
        """Report the write result and reconcile state after device interaction."""
        if not success:
            _LOGGER.warning(
                "%s fan write did not complete successfully", self._fan_type
            )
        await self.coordinator.async_request_refresh()

    async def async_turn_on(
        self,
        percentage: int | None = None,
        preset_mode: str | None = None,
        **kwargs: Any,
    ) -> None:
        """Turn on the fan."""
        if percentage is not None:
            await self.async_set_percentage(percentage)
            return
        success = await self.hass.async_add_executor_job(self._system.set_power, True)
        await self._async_refresh_after_write(success)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the fan off."""
        success = await self.hass.async_add_executor_job(self._system.set_power, False)
        await self._async_refresh_after_write(success)

    async def async_set_percentage(self, percentage: int) -> None:
        """Set the speed percentage of the fan."""
        if percentage == 0:
            await self.async_turn_off()
            return

        speed = percentage_to_ordered_list_item(ORDERED_NAMED_FAN_SPEEDS, percentage)

        already_on = self.coordinator.last_update_success and self._attr_is_on

        def write_speed_then_power() -> bool:
            # Speed and power are non-contiguous registers, so this sequence
            # cannot be atomic. Never power on if selecting the speed failed.
            if self._fan_type == "supply":
                speed_success = self._system.set_supply_speed(speed)
            else:
                speed_success = self._system.set_exhaust_speed(speed)
            if not speed_success:
                return False
            if already_on:
                return True
            return self._system.set_power(True)

        success = await self.hass.async_add_executor_job(write_speed_then_power)
        await self._async_refresh_after_write(success)

    async def async_toggle(self, **kwargs: Any) -> None:
        """Toggle the fan."""
        if self._attr_is_on:
            await self.async_turn_off(**kwargs)
        else:
            await self.async_turn_on(**kwargs)
