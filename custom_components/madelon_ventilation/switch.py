from __future__ import annotations

from .const import DOMAIN
from .fresh_air_controller import FreshAirSystem
from typing import Any

from homeassistant.components.switch import SwitchDeviceClass, SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.device_registry import DeviceInfo
import logging

async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Fresh Air System switch based on a config entry."""
    # 从 hass.data 中获取 FreshAirSystem 实例
    logging.getLogger(__name__).info("Setting up Fresh Air System switch")

    # host = config_entry.data[CONF_HOST]
    # system = FreshAirSystem(host)
    # system = hass.data[DOMAIN]["system"]
    
    # 添加开关实体
    async_add_entities([FreshAirPowerSwitch(hass.data[DOMAIN][config_entry.entry_id]["system"])])

class FreshAirPowerSwitch(SwitchEntity):
    _attr_device_class = SwitchDeviceClass.SWITCH

    def __init__(self, system):
        super().__init__()
        self._attr_has_entity_name = True
        self._system = system
        self._attr_name = "Fresh Air Power"
        self._attr_unique_id = f"{DOMAIN}_power_switch_{system.unique_identifier}"
        self._attr_is_on = system.power

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

    async def async_turn_on(self, **kwargs):
        self._system.power = True
        self._attr_is_on = True
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs):
        self._system.power = False
        self._attr_is_on = False
        self.async_write_ha_state()

    async def async_update(self):
        self._attr_is_on = self._system.power