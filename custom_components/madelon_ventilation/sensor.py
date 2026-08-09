import logging

from homeassistant.components.sensor import (  # pyright: ignore[reportMissingImports]
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry  # pyright: ignore[reportMissingImports]
from homeassistant.const import (  # pyright: ignore[reportMissingImports]
    PERCENTAGE,
    UnitOfTemperature,
    UnitOfTime,
)
from homeassistant.helpers.device_registry import (  # pyright: ignore[reportMissingImports]
    DeviceInfo,
)

from .const import (
    DEVICE_MANUFACTURER,
    DEVICE_MODEL,
    DEVICE_SW_VERSION,
    DOMAIN,
)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the Fresh Air System sensors."""
    logging.getLogger(__name__).info("Setting up Fresh Air System sensors")
    fresh_air_system = hass.data[DOMAIN][config_entry.entry_id]["system"]

    temperature_sensor = FreshAirTemperatureSensor(config_entry, fresh_air_system)
    humidity_sensor = FreshAirHumiditySensor(config_entry, fresh_air_system)
    filter_usage_sensor = FreshAirFilterUsageSensor(config_entry, fresh_air_system)
    all_sensors = [temperature_sensor, humidity_sensor, filter_usage_sensor]

    # Register sensors with the system
    fresh_air_system.register_sensor(temperature_sensor)
    fresh_air_system.register_sensor(humidity_sensor)
    fresh_air_system.register_sensor(filter_usage_sensor)

    # Store sensors in hass.data for other platforms (e.g., fan) to access
    hass.data[DOMAIN][config_entry.entry_id]["sensors"] = all_sensors

    async_add_entities(all_sensors)


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
    def available(self) -> bool:
        """Return whether the controller can currently be read."""
        return self._system.available

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
        try:
            value = self._system.temperature
            if self._system.available and value is not None:
                self._attr_native_value = value
        except Exception as e:
            logging.getLogger(__name__).error(f"Error updating temperature sensor: {e}")


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
    def available(self) -> bool:
        """Return whether the controller can currently be read."""
        return self._system.available

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
        try:
            value = self._system.humidity
            if self._system.available and value is not None:
                self._attr_native_value = value
        except Exception as e:
            logging.getLogger(__name__).error(f"Error updating humidity sensor: {e}")


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
    def available(self) -> bool:
        """Return whether the controller can currently be read."""
        return self._system.available

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
        try:
            value = self._system.filter_usage_time
            if self._system.available and value is not None:
                self._attr_native_value = value
                logging.getLogger(__name__).debug(
                    f"Filter usage time updated: {self._attr_native_value} hours"
                )
        except Exception as e:
            logging.getLogger(__name__).error(
                f"Error updating filter usage time sensor: {e}"
            )
