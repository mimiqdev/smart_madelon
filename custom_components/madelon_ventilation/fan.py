from homeassistant.components.fan import FanEntity, SUPPORT_SET_SPEED
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.const import CONF_HOST
from .const import DOMAIN
from .fresh_air_controller import FreshAirSystem
import logging

async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the Fresh Air System fan."""
    logging.getLogger(__name__).info("Setting up Fresh Air System fan")
    async_add_entities([FreshAirFan(config_entry, hass.data[DOMAIN][config_entry.entry_id]["system"])])

class FreshAirFan(FanEntity):
    def __init__(self, entry: ConfigEntry, system):
        super().__init__()
        self._attr_has_entity_name = True
        self._system = system
        self._attr_name = "Fresh Air Fan"
        self._attr_is_on = False
        self._attr_percentage = self._get_percentage(0)
        self._attr_unique_id = f"{DOMAIN}_fan_{system.unique_identifier}"
        # self._update_state_from_system()

    def _update_state_from_system(self):
        """Update the fan's state from the FreshAirSystem."""
        self._attr_is_on = self._system.power
        self._attr_percentage = self._get_percentage(self._system.supply_speed)
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
        return SUPPORT_SET_SPEED

    @property
    def is_on(self):
        """Return true if the fan is on."""
        return self._system.power

    @property
    def percentage(self):
        """Return the current speed as a percentage."""
        return self._get_percentage(self._system.supply_speed)

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

    async def async_turn_on(self, percentage=None, **kwargs):
        """Turn on the fan."""
        if not self._system.power:
            self._system.power = True
        if percentage is not None:
            await self.async_set_percentage(percentage)
        self._update_state_from_system()

    async def async_turn_off(self, **kwargs):
        """Turn off the fan."""
        self._system.power = False
        self._attr_percentage = 0
        self._update_state_from_system()

    async def async_set_percentage(self, percentage):
        """Set the speed of the fan as a percentage."""
        speed_value = self._get_speed_value(percentage)

        if speed_value == 0:
            await self.async_turn_off()
        else:
            if not self._system.power:
                self._system.power = True
            self._system.supply_speed = speed_value
            self._attr_percentage = percentage
            self._update_state_from_system() 