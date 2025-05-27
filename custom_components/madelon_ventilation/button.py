from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from .const import (
    DOMAIN,
    DEVICE_MANUFACTURER,
    DEVICE_MODEL,
    DEVICE_SW_VERSION,
)
from .fresh_air_controller import FreshAirSystem
import logging


async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry, async_add_entities: AddEntitiesCallback):
    """Set up the Fresh Air System buttons."""
    logging.getLogger(__name__).info("Setting up Fresh Air System buttons")
    system = hass.data[DOMAIN][config_entry.entry_id]["system"]

    # Create filter reset button
    filter_reset_button = FilterResetButton(config_entry, system)
    async_add_entities([filter_reset_button])


class FilterResetButton(ButtonEntity):
    """Button to reset filter usage time."""

    def __init__(self, entry: ConfigEntry, system: FreshAirSystem):
        super().__init__()
        self._system = system
        self._attr_has_entity_name = True
        self._attr_name = "Reset Filter Usage"
        self._attr_unique_id = f"{entry.entry_id}_filter_reset"
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
        try:
            # Reset filter usage time
            result = await self.hass.async_add_executor_job(self._system.reset_filter_usage_time)
            if result:
                logging.getLogger(__name__).info("Filter usage time reset successfully")
                # Update all sensors to reflect the change
                for sensor in self._system.sensors:
                    sensor.schedule_update_ha_state(True)
            else:
                logging.getLogger(__name__).error("Failed to reset filter usage time")
        except Exception as e:
            logging.getLogger(__name__).error(f"Error resetting filter usage time: {e}", exc_info=True) 