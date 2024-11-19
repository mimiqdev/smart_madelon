from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from .const import DOMAIN
from .fresh_air_controller import FreshAirSystem
import logging

async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry, async_add_entities: AddEntitiesCallback):
    """Set up the Fresh Air System mode select."""
    logging.getLogger(__name__).info("Setting up Fresh Air System mode select")
    system = hass.data[DOMAIN][config_entry.entry_id]["system"]
    async_add_entities([FreshAirModeSelect(config_entry, system)])

class FreshAirModeSelect(SelectEntity):
    def __init__(self, entry: ConfigEntry, system: FreshAirSystem):
        super().__init__()
        self._system = system
        self._attr_name = "Fresh Air Mode"
        self._attr_unique_id = f"{DOMAIN}_mode_select_{system.unique_identifier}"
        self._attr_options = [
            "manual", "auto", "timer",
            "manual_bypass", "auto_bypass", "timer_bypass"
        ]
        self._attr_current_option = self._get_mode_from_system()

    def _get_mode_from_system(self):
        """Get the current mode from the system."""
        mode_map = {
            (0, False): "manual",
            (1, False): "auto",
            (2, False): "timer",
            (0, True): "manual_bypass",
            (1, True): "auto_bypass",
            (2, True): "timer_bypass"
        }
        return mode_map.get((self._system.mode, self._system.bypass), "manual")

    async def async_select_option(self, option: str):
        """Change the selected option."""
        mode_map = {
            "manual": (0, False),
            "auto": (1, False),
            "timer": (2, False),
            "manual_bypass": (0, True),
            "auto_bypass": (1, True),
            "timer_bypass": (2, True)
        }
        if option in mode_map:
            mode, bypass = mode_map[option]
            self._system.mode = mode
            self._system.bypass = bypass
            self._attr_current_option = option
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
