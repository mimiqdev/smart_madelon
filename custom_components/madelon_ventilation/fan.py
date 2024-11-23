from homeassistant.components.fan import FanEntity, FanEntityFeature
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_time_interval
from datetime import timedelta
from .const import DOMAIN
from .fresh_air_controller import FreshAirSystem
import logging
from typing import Any

async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry, async_add_entities: AddEntitiesCallback):
    """Set up the Fresh Air System fan."""
    logging.getLogger(__name__).info("Setting up Fresh Air System fan")
    system = hass.data[DOMAIN][config_entry.entry_id]["system"]
    fan = FreshAirFan(config_entry, system)
    async_add_entities([fan])

    # Schedule regular updates for the FreshAirSystem cache
    async_track_time_interval(hass, fan.async_update, timedelta(seconds=30))

class FreshAirFan(FanEntity):
    def __init__(self, entry: ConfigEntry, system: FreshAirSystem):
        super().__init__()
        self._attr_has_entity_name = True
        self._system = system
        self._attr_name = "Fresh Air Fan"
        self._attr_unique_id = f"{DOMAIN}_fan_{system.unique_identifier}"
        self._attr_percentage = 0

    async def async_update(self, now=None):
        """Fetch new state data for the fan."""
        try:
            self._system._read_all_registers()
            if self._system.available:
                self._attr_is_on = self._system.power
                self._attr_percentage = self._get_percentage(self._system.supply_speed)
            self._attr_available = self._system.available
        except Exception as e:
            self.logger.error(f"Error updating fan state: {e}")
            self._attr_available = False
        
        self.async_write_ha_state()

    def _update_state_from_system(self):
        """Update the fan's state from the FreshAirSystem."""
        if self._system.available:
            self._attr_is_on = self._system.power
            self._attr_percentage = self._get_percentage(self._system.supply_speed)
        self._attr_available = self._system.available
        self.async_write_ha_state()

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information about this entity."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._system.unique_identifier)},
            name="Fresh Air System",
            manufacturer="Madelon",
            model="XIXI",
            sw_version="1.0",
        )

    @property
    def supported_features(self):
        """Flag supported features."""
        return (
            FanEntityFeature.SET_SPEED |
            FanEntityFeature.TURN_ON |
            FanEntityFeature.TURN_OFF
        )

    @property
    def is_on(self):
        """Return true if the fan is on."""
        return self._attr_is_on

    @property
    def percentage(self):
        """Return the current speed as a percentage."""
        return self._attr_percentage

    @property
    def speed_count(self):
        """Return the number of speeds the fan supports."""
        return 3  # low, medium, high

    def _get_percentage(self, speed_value):
        """Convert speed value to percentage."""
        speed_map = {0: 0, 1: 33, 2: 66, 3: 100}
        return speed_map.get(speed_value, 0)

    def _get_speed_value(self, percentage):
        """Convert percentage to speed value."""
        if percentage == 0:
            return 0
        elif percentage <= 33:
            return 1
        elif percentage <= 66:
            return 2
        else:
            return 3

    async def async_turn_on(
        self,
        speed: str | None = None,
        percentage: int | None = None,
        preset_mode: str | None = None,
        **kwargs: Any
    ) -> None:
        """Turn on the fan."""
        self._system.power = True
        
        # Handle percentage if provided (preferred method)
        if percentage is not None:
            speed_value = self._get_speed_value(percentage)
            self._system.supply_speed = speed_value
            self._system.exhaust_speed = speed_value
            self._attr_percentage = percentage
        # Handle legacy speed if provided
        elif speed is not None:
            # Convert legacy speed string to percentage
            if speed == "low":
                self._attr_percentage = 33
            elif speed == "medium":
                self._attr_percentage = 66
            elif speed == "high":
                self._attr_percentage = 100
            speed_value = self._get_speed_value(self._attr_percentage)
            self._system.supply_speed = speed_value
            self._system.exhaust_speed = speed_value

        # Handle preset_mode if provided
        if preset_mode is not None:
            # Implement preset mode handling if your fan supports it
            pass

        self._attr_is_on = True
        # Update the entity state by reading from the device
        await self.async_update()

    async def async_turn_off(self, **kwargs) -> None:
        """Turn the fan off.""" 
        self._system.power = False
        self._attr_percentage = 0
        await self.async_update()

    async def async_set_percentage(self, percentage):
        """Set the speed of the fan as a percentage."""
        speed_value = self._get_speed_value(percentage)

        if speed_value == 0:
            self._system.power = False
        else:
            self._system.power = True
            self._system.supply_speed = speed_value
            self._system.exhaust_speed = speed_value

        self._attr_percentage = percentage
        await self.async_update()
