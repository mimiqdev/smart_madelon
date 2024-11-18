from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from .const import DOMAIN
from .fresh_air_controller import FreshAirSystem
import logging

async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up the Madelon Ventilation component."""
    logging.getLogger(__name__).info("Setting up Madelon Ventilation")
    host = config[DOMAIN].get("host")
    system = FreshAirSystem(host)
    hass.data[DOMAIN] = {"system": system}
    return True

async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Set up the Fresh Air System from a config entry."""
    await hass.config_entries.async_forward_entry_setup(config_entry, "fan")
    await hass.config_entries.async_forward_entry_setup(config_entry, "sensor")
    await hass.config_entries.async_forward_entry_setup(config_entry, "switch")

    return True