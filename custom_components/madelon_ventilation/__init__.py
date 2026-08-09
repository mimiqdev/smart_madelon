"""Madelon Ventilation integration."""

from __future__ import annotations

# pyright: reportMissingImports=false

import logging
from datetime import timedelta

from homeassistant.config_entries import (
    ConfigEntry,  # pyright: ignore[reportMissingImports]
)
from homeassistant.const import (  # pyright: ignore[reportMissingImports]
    CONF_HOST,
    CONF_PORT,
    CONF_SCAN_INTERVAL,
    Platform,
)
from homeassistant.core import HomeAssistant  # pyright: ignore[reportMissingImports]

from .const import (
    CONF_UNIT_ID,
    DEFAULT_PORT,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_UNIT_ID,
    DOMAIN,
)
from .coordinator import MadelonVentilationCoordinator  # pyright: ignore[reportMissingImports]
from .fresh_air_controller import FreshAirSystem

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [
    Platform.SENSOR,
    Platform.FAN,
    Platform.SWITCH,
    Platform.BUTTON,
]


async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Set up the Fresh Air System from a config entry."""
    system = FreshAirSystem(
        host=config_entry.data[CONF_HOST],
        port=config_entry.data.get(CONF_PORT, DEFAULT_PORT),
        unit_id=config_entry.data.get(CONF_UNIT_ID, DEFAULT_UNIT_ID),
    )
    system.enable_coordinator_mode()
    coordinator = MadelonVentilationCoordinator(
        hass,
        config_entry,
        system,
        timedelta(
            seconds=config_entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
        ),
    )

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][config_entry.entry_id] = {
        "system": system,
        "coordinator": coordinator,
    }
    config_entry.async_on_unload(config_entry.add_update_listener(async_reload_entry))
    _LOGGER.info("Setting up Madelon Ventilation entry")

    # Do not use async_config_entry_first_refresh: an offline device must not
    # delay platform setup. CoordinatorEntity will expose the failed refresh.
    await coordinator.async_refresh()
    await hass.config_entries.async_forward_entry_setups(config_entry, PLATFORMS)
    return True


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload an entry after its options change."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        entry_data = hass.data[DOMAIN][entry.entry_id]
        await hass.async_add_executor_job(entry_data["system"].modbus.close)
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
