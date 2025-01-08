from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.device_registry import DeviceInfo
from .const import DOMAIN
from .fresh_air_controller import FreshAirSystem
from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.const import UnitOfTemperature, PERCENTAGE, CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
import logging


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the Fresh Air System sensors."""
    logging.getLogger(__name__).info("Setting up Fresh Air System sensors")
    fresh_air_system = hass.data[DOMAIN][config_entry.entry_id]["system"]

    temperature_sensor = FreshAirTemperatureSensor(config_entry, fresh_air_system)
    humidity_sensor = FreshAirHumiditySensor(config_entry, fresh_air_system)

    # Register sensors with the system
    fresh_air_system.register_sensor(temperature_sensor)
    fresh_air_system.register_sensor(humidity_sensor)

    async_add_entities([temperature_sensor, humidity_sensor])


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

    async def async_update(self):
        self._attr_native_value = self._system.humidity
