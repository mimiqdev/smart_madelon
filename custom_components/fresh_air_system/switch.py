from homeassistant.components.switch import SwitchEntity
from .const import DOMAIN

async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the Fresh Air System switch."""
    # 从 hass.data 中获取 FreshAirSystem 实例
    system = hass.data[DOMAIN]["system"]
    
    # 添加开关实体
    async_add_entities([FreshAirPowerSwitch(system)])

class FreshAirPowerSwitch(SwitchEntity):
    def __init__(self, system):
        self._system = system
        self._attr_name = "Fresh Air Power"
        self._attr_is_on = system.power

    async def async_turn_on(self, **kwargs):
        self._system.power = True
        self._attr_is_on = True
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs):
        self._system.power = False
        self._attr_is_on = False
        self.async_write_ha_state()