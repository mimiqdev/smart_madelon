from typing import Any, Optional
from homeassistant.components.fan import FanEntity, FanEntityFeature
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_time_interval

# Helper function for percentage conversion
from homeassistant.util.percentage import (
    ordered_list_item_to_percentage,
    percentage_to_ordered_list_item,
)
from datetime import timedelta
from .const import (
    DOMAIN,
    DEVICE_MANUFACTURER,
    DEVICE_MODEL,
    DEVICE_SW_VERSION,
)
from .fresh_air_controller import FreshAirSystem
import logging

ORDERED_NAMED_FAN_SPEEDS = ["low", "medium", "high"]  # off is not included


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
):
    """Set up the Fresh Air System fans."""
    logging.getLogger(__name__).info("Setting up Fresh Air System fans")
    system = hass.data[DOMAIN][config_entry.entry_id]["system"]

    # Create both supply and exhaust fan entities using the same class
    supply_fan = FreshAirFan(config_entry, system, "supply")
    exhaust_fan = FreshAirFan(config_entry, system, "exhaust")
    async_add_entities([supply_fan, exhaust_fan])

    # Schedule regular updates
    async def async_update(now=None):
        """Update the entities."""
        logging.getLogger(__name__).debug("Updating fan and sensor states...")
        try:
            # Update both fans
            await hass.async_add_executor_job(supply_fan.update)
            await hass.async_add_executor_job(exhaust_fan.update)

            # Update states for fans
            if supply_fan.hass and supply_fan.available:
                supply_fan.async_write_ha_state()
            if exhaust_fan.hass and exhaust_fan.available:
                exhaust_fan.async_write_ha_state()

            # Update sensors
            sensors = hass.data[DOMAIN][config_entry.entry_id].get("sensors", [])
            for sensor in sensors:
                if (
                    sensor.hass and sensor.should_poll
                ):  # Ensure sensor is added and needs polling
                    await hass.async_add_executor_job(sensor.update)
                    if sensor.available:
                        sensor.async_write_ha_state()
                        logging.getLogger(__name__).debug(
                            f"Sensor {sensor.name} data updated. New native_value: {sensor.native_value}"
                        )

        except Exception as e:
            logging.getLogger(__name__).error(
                f"Error updating fan and sensor states: {e}", exc_info=True
            )

    # Use event scheduler for periodic updates
    unsub = async_track_time_interval(hass, async_update, timedelta(seconds=30))
    config_entry.async_on_unload(unsub)


class FreshAirFan(FanEntity):
    """Fresh Air System fan entity."""

    def __init__(self, entry: ConfigEntry, system: FreshAirSystem, fan_type: str):
        super().__init__()
        self._system = system
        self._fan_type = fan_type.lower()  # 'supply' or 'exhaust'
        self._attr_has_entity_name = True
        self._attr_name = f"{fan_type.capitalize()} Fan"
        self._attr_is_on = False
        self._attr_percentage = 0
        self._attr_unique_id = (
            f"{DOMAIN}_{self._fan_type}_fan_{system.unique_identifier}"
        )
        # Remove preset modes to prevent them from showing in HomeKit
        self._attr_preset_modes = None
        self._attr_preset_mode = None

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
    def supported_features(self):
        """Flag supported features."""
        return (
            FanEntityFeature.SET_SPEED
            | FanEntityFeature.TURN_ON
            | FanEntityFeature.TURN_OFF
        )

    @property
    def is_on(self):
        """Return true if the fan is on."""
        return self._attr_is_on

    @property
    def percentage(self) -> Optional[int]:
        """Return the current speed percentage."""
        return self._attr_percentage

    async def async_added_to_hass(self) -> None:
        """Run when entity about to be added to hass."""
        await super().async_added_to_hass()
        # Initial update
        await self.hass.async_add_executor_job(self.update)

    def update(self):
        """Update the fan's state."""
        try:
            power = self._system.power

            # Get speed based on fan type
            if self._fan_type == "supply":
                speed = self._system.supply_speed
            else:  # exhaust
                speed = self._system.exhaust_speed

            self._attr_is_on = power if power is not None else False

            # Calculate percentage
            if not self._attr_is_on or speed is None:
                self._attr_percentage = 0
            else:
                try:
                    self._attr_percentage = ordered_list_item_to_percentage(
                        ORDERED_NAMED_FAN_SPEEDS, speed
                    )
                except ValueError:
                    logging.getLogger(__name__).warning(
                        f"Invalid {self._fan_type} speed value: {speed}"
                    )
                    self._attr_percentage = 0

        except Exception as e:
            logging.getLogger(__name__).error(
                f"Error in {self._fan_type} fan update: {e}", exc_info=True
            )

    def turn_on(
        self,
        percentage: Optional[int] = None,
        preset_mode: Optional[str] = None,
        **kwargs: Any,
    ) -> None:
        """Turn on the fan.

        Args:
            percentage: Optional speed percentage to set (0-100). If provided,
                       the fan will turn on at this speed.
            preset_mode: Optional preset mode to set. Not currently implemented.
            **kwargs: Additional arguments that might be supported in the future.

        Returns:
            None

        Note:
            If no percentage is provided, the fan will turn on at its last known speed.
        """
        if percentage is not None:
            self.set_percentage(percentage)
        else:
            self._system.power = True
        self.update()

    def turn_off(self, **kwargs: Any) -> None:
        """Turn the fan off.

        Args:
            **kwargs: Additional arguments that might be supported in the future.

        Returns:
            None

        Note:
            This will completely stop the fan and set its state to off.
        """
        self._system.power = False
        self.update()

    def set_percentage(self, percentage: int):
        """Set the speed percentage of the fan."""
        if percentage == 0:
            self.turn_off()
            return

        self._system.power = True
        speed = percentage_to_ordered_list_item(ORDERED_NAMED_FAN_SPEEDS, percentage)

        # Set speed based on fan type
        if self._fan_type == "supply":
            self._system.supply_speed = speed
        else:  # exhaust
            self._system.exhaust_speed = speed

        self.update()

    def toggle(self, **kwargs: Any) -> None:
        """Toggle the fan."""
        if self._attr_is_on:
            self.turn_off(**kwargs)
        else:
            self.turn_on(**kwargs)
