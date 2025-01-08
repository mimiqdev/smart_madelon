from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.const import Platform, CONF_HOST, CONF_PORT
from homeassistant.helpers.discovery import async_load_platform
from .const import DOMAIN, DEFAULT_PORT, DEFAULT_UNIT_ID, CONF_UNIT_ID

from .fresh_air_controller import FreshAirSystem
import logging

PLATFORMS: list[Platform] = [Platform.SENSOR, Platform.FAN, Platform.SWITCH]


async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Set up the Fresh Air System from a config entry."""
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][config_entry.entry_id] = {
        "system": FreshAirSystem(
            host=config_entry.data[CONF_HOST],
            port=config_entry.data.get(CONF_PORT, DEFAULT_PORT),
            unit_id=config_entry.data.get(CONF_UNIT_ID, DEFAULT_UNIT_ID)
        )
    }
    logging.getLogger(__name__).info("Setting up Madelon Ventilation entry")

    # Forward the setup to the platforms
    await hass.config_entries.async_forward_entry_setups(config_entry, PLATFORMS)
    return True

# async def async_remove_config_entry_device(
#     hass: HomeAssistant, config_entry: ConfigEntry, device_entry: DeviceEntry
# ) -> bool:
#     """Delete device if selected from UI."""
#     # Adding this function shows the delete device option in the UI.
#     # Remove this function if you do not want that option.
#     # You may need to do some checks here before allowing devices to be removed.
#     return True
