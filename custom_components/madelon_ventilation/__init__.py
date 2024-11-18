from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.const import Platform
from homeassistant.helpers.discovery import async_load_platform
from .const import DOMAIN

from .fresh_air_controller import FreshAirSystem
import logging

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
    try:
        await hass.config_entries.async_forward_entry_setup(config_entry, Platform.FAN)
        logger.info("Forwarded FAN platform setup successfully.")
        
        await hass.config_entries.async_forward_entry_setup(config_entry, Platform.SENSOR)
        logger.info("Forwarded SENSOR platform setup successfully.")
        
        await hass.config_entries.async_forward_entry_setup(config_entry, Platform.SWITCH)
        logger.info("Forwarded SWITCH platform setup successfully.")
        
        return True
    except Exception as e:
        logger.error(f"Error setting up entry: {e}")
        return False