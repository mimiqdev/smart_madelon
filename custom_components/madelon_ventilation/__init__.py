from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.const import Platform
from homeassistant.helpers.discovery import async_load_platform
from .const import DOMAIN

from .fresh_air_controller import FreshAirSystem
import logging

PLATFORMS: list[Platform] = [Platform.SENSOR, Platform.FAN, Platform.SWITCH]

async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up the Madelon Ventilation component."""
    logging.getLogger(__name__).info("Setting up Madelon Ventilation")
    host = config[DOMAIN].get("host")
    # hass.async_create_task(async_load_platform(hass, Platform.FAN, DOMAIN, {}, config))
    # hass.async_create_task(async_load_platform(hass, Platform.SENSOR, DOMAIN, {}, config))
    # hass.async_create_task(async_load_platform(hass, Platform.SWITCH, DOMAIN, {}, config))
    system = FreshAirSystem(host)
    hass.data[DOMAIN] = {"system": system}
    return True

async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Set up the Fresh Air System from a config entry."""
    logger = logging.getLogger(__name__)
    await hass.config_entries.async_forward_entry_setups(config_entry, PLATFORMS)
    return True