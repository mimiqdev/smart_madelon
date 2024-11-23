from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from .const import DOMAIN
from .fresh_air_controller import FreshAirSystem, OperationMode
import logging
import asyncio

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
            "Manual", "Auto", "Timer",
            "Manual Bypass", "Auto Bypass", "Timer Bypass"
        ]
        self._attr_current_option = self._get_mode_from_system()

    def _get_mode_from_system(self):
        """Get the current mode from the system."""
        mode_map = {
            (OperationMode.MANUAL, False): "Manual",
            (OperationMode.AUTO, False): "Auto",
            (OperationMode.TIMER, False): "Timer",
            (OperationMode.MANUAL, True): "Manual Bypass",
            (OperationMode.AUTO, True): "Auto Bypass",
            (OperationMode.TIMER, True): "Timer Bypass"
        }
        return mode_map.get((self._system.mode, self._system.bypass), "Manual")

    async def async_select_option(self, option: str):
        """Change the selected option."""
        from .fresh_air_controller import OperationMode
        
        mode_map = {
            "Manual": (OperationMode.MANUAL, False),
            "Auto": (OperationMode.AUTO, False),
            "Timer": (OperationMode.TIMER, False),
            "Manual Bypass": (OperationMode.MANUAL, True),
            "Auto Bypass": (OperationMode.AUTO, True),
            "Timer Bypass": (OperationMode.TIMER, True)
        }
        if option in mode_map:
            mode, bypass = mode_map[option]
            # Set mode first
            self._system.mode = mode
            # Wait for 300ms
            await asyncio.sleep(0.3)
            # Then set bypass
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
            model="Jinmaofu",
            sw_version="0.1.0",
        )
