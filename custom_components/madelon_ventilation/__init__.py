from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.const import Platform
from homeassistant.const import CONF_HOST
from homeassistant.helpers.discovery import async_load_platform
from .const import DOMAIN

from .fresh_air_controller import FreshAirSystem
import logging

PLATFORMS: list[Platform] = [Platform.SENSOR, Platform.FAN, Platform.SWITCH]

# async def async_setup(hass: HomeAssistant, entry: ConfigEntry) -> bool:
#     """Set up the Madelon Ventilation component."""
#     logging.getLogger(__name__).info("Setting up Madelon Ventilation")

#     hass.data.setdefault(DOMAIN, {})
#     host = entry.data[CONF_HOST]
#     system = FreshAirSystem(host)
#     hass.data[DOMAIN] = {"system": system}
#     return True

async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Set up the Fresh Air System from a config entry."""
    hass.data.setdefault(DOMAIN, {})
    hass_data = dict(hass.data[DOMAIN])
    hass.data[DOMAIN][config_entry.entry_id] = hass_data
    host = config_entry.data[CONF_HOST]
    system = FreshAirSystem(host)
    hass.data[DOMAIN][config_entry.entry_id]['system'] = system
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