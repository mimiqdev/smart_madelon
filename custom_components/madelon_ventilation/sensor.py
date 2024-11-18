from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.entity import DeviceInfo
from .const import DOMAIN
from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.const import UnitOfTemperature, PERCENTAGE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
import logging

async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the Fresh Air System sensors."""
    logging.getLogger(__name__).info("Setting up Fresh Air System sensors")
    # 从 hass.data 中获取 FreshAirSystem 实例
    system = hass.data[DOMAIN]["system"]

    # 添加传感器实体
    async_add_entities([
        FreshAirTemperatureSensor(config_entry, system),
        FreshAirHumiditySensor(config_entry, system)
    ])

async def async_setup_platform(hass, config_entry, async_add_entities, discovery_info=None):
    """Set up the Fresh Air System sensors."""
    logging.getLogger(__name__).info("Setting up Fresh Air System sensors")
    # 从 hass.data 中获取 FreshAirSystem 实例
    system = hass.data[DOMAIN]["system"]

    async_add_entities([
        FreshAirTemperatureSensor(config_entry, system),
        FreshAirHumiditySensor(config_entry, system)
    ])

class FreshAirTemperatureSensor(SensorEntity):
    _attr_has_entity_name = True
    _attr_name = "Fresh Air Temperature"
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_device_class = SensorDeviceClass.TEMPERATURE

    def __init__(self, entry: ConfigEntry, system):
        super().__init__()
        self._system = system
        self._attr_unique_id = f"{DOMAIN}_temperature_sensor_{system.unique_identifier}"
        self._attr_native_value = None

    async def async_update(self):
        self._attr_native_value = self._system.temperature

class FreshAirHumiditySensor(SensorEntity):
    _attr_has_entity_name = True
    _attr_name = "Fresh Air Humidity"
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_device_class = SensorDeviceClass.HUMIDITY

    def __init__(self, entry: ConfigEntry, system):
        super().__init__()
        self._system = system
        self._attr_unique_id = f"{DOMAIN}_humidity_sensor_{system.unique_identifier}"
        self._attr_native_value = None

    async def async_update(self):
        self._attr_native_value = self._system.humidity