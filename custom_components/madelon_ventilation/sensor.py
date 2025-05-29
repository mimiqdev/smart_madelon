from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.device_registry import DeviceInfo
from .const import (
    DOMAIN,
    DEVICE_MANUFACTURER,
    DEVICE_MODEL,
    DEVICE_SW_VERSION,
)
from .fresh_air_controller import FreshAirSystem
from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.const import UnitOfTemperature, PERCENTAGE, CONF_HOST, UnitOfTime
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
    filter_usage_sensor = FreshAirFilterUsageSensor(config_entry, fresh_air_system)

    # Register sensors with the system
    fresh_air_system.register_sensor(temperature_sensor)
    fresh_air_system.register_sensor(humidity_sensor)
    fresh_air_system.register_sensor(filter_usage_sensor)

    async_add_entities([temperature_sensor, humidity_sensor, filter_usage_sensor])


class FreshAirTemperatureSensor(SensorEntity):
    _attr_has_entity_name = True
    _attr_name = "Temperature"
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_device_class = SensorDeviceClass.TEMPERATURE

    def __init__(self, entry: ConfigEntry, system):
        super().__init__()
        self._system = system
        self._attr_unique_id = f"{DOMAIN}_{system.unique_identifier}_temperature"
        self._attr_native_value = None

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information about this entity."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._system.unique_identifier)},
            name="Fresh Air System",
            manufacturer=DEVICE_MANUFACTURER,
            model=DEVICE_MODEL,
            sw_version=DEVICE_SW_VERSION,
        )

    def update(self) -> None:
        """Update the sensor."""
        self._attr_native_value = self._system.temperature


class FreshAirHumiditySensor(SensorEntity):
    _attr_has_entity_name = True
    _attr_name = "Humidity"
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_device_class = SensorDeviceClass.HUMIDITY

    def __init__(self, entry: ConfigEntry, system):
        super().__init__()
        self._system = system
        self._attr_unique_id = f"{DOMAIN}_{system.unique_identifier}_humidity"
        self._attr_native_value = None

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information about this entity."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._system.unique_identifier)},
            name="Fresh Air System",
            manufacturer=DEVICE_MANUFACTURER,
            model=DEVICE_MODEL,
            sw_version=DEVICE_SW_VERSION,
        )

    def update(self) -> None:
        """Update the sensor."""
        self._attr_native_value = self._system.humidity


class FreshAirFilterUsageSensor(SensorEntity):
    _attr_has_entity_name = True
    _attr_name = "Filter Usage Time"
    _attr_native_unit_of_measurement = UnitOfTime.HOURS
    _attr_state_class = SensorStateClass.TOTAL_INCREASING
    _attr_icon = "mdi:air-filter"

    def __init__(self, entry: ConfigEntry, system):
        super().__init__()
        self._system = system
        self._attr_unique_id = f"{DOMAIN}_{system.unique_identifier}_filter_usage_time"
        self._attr_native_value = None

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information about this entity."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._system.unique_identifier)},
            name="Fresh Air System",
            manufacturer=DEVICE_MANUFACTURER,
            model=DEVICE_MODEL,
            sw_version=DEVICE_SW_VERSION,
        )

    def update(self) -> None:
        """Update the sensor."""
        self._attr_native_value = self._system.filter_usage_time
