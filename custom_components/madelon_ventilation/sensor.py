"""Sensor platform for Madelon Ventilation."""

from __future__ import annotations

# pyright: reportMissingImports=false

from homeassistant.components.sensor import (  # pyright: ignore[reportMissingImports]
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import (
    ConfigEntry,  # pyright: ignore[reportMissingImports]
)
from homeassistant.const import (  # pyright: ignore[reportMissingImports]
    PERCENTAGE,
    UnitOfTemperature,
    UnitOfTime,
)
from homeassistant.core import (  # pyright: ignore[reportMissingImports]
    HomeAssistant,
    callback,
)
from homeassistant.helpers.device_registry import (  # pyright: ignore[reportMissingImports]
    DeviceInfo,
)
from homeassistant.helpers.entity_platform import (  # pyright: ignore[reportMissingImports]
    AddEntitiesCallback,
)
from homeassistant.helpers.update_coordinator import (  # pyright: ignore[reportMissingImports]
    CoordinatorEntity,
)

from .const import DEVICE_MANUFACTURER, DEVICE_MODEL, DEVICE_SW_VERSION, DOMAIN
from .coordinator import MadelonVentilationCoordinator  # pyright: ignore[reportMissingImports]
from .fresh_air_controller import FreshAirSystem


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Fresh Air System sensors."""
    coordinator = hass.data[DOMAIN][config_entry.entry_id]["coordinator"]
    async_add_entities(
        [
            FreshAirTemperatureSensor(coordinator),
            FreshAirHumiditySensor(coordinator),
            FreshAirFilterUsageSensor(coordinator),
        ]
    )


class FreshAirSensorEntity(
    CoordinatorEntity[MadelonVentilationCoordinator], SensorEntity
):
    """Base class for sensors using the shared register snapshot."""

    def __init__(self, coordinator: MadelonVentilationCoordinator) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._system: FreshAirSystem = coordinator.system
        self._attr_native_value = None
        if coordinator.last_update_success:
            self._update_from_snapshot()

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

    def _update_from_snapshot(self) -> None:
        """Copy state from the latest successful shared snapshot."""
        raise NotImplementedError

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle a shared register snapshot update."""
        if self.coordinator.last_update_success:
            self._update_from_snapshot()
        super()._handle_coordinator_update()


class FreshAirTemperatureSensor(FreshAirSensorEntity):
    """Fresh Air System temperature sensor."""

    _attr_has_entity_name = True
    _attr_name = "Temperature"
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_device_class = SensorDeviceClass.TEMPERATURE

    def __init__(self, coordinator: MadelonVentilationCoordinator) -> None:
        """Initialize the temperature sensor."""
        self._attr_unique_id = (
            f"{DOMAIN}_{coordinator.system.unique_identifier}_temperature"
        )
        super().__init__(coordinator)

    def _update_from_snapshot(self) -> None:
        self._attr_native_value = self._system.temperature


class FreshAirHumiditySensor(FreshAirSensorEntity):
    """Fresh Air System humidity sensor."""

    _attr_has_entity_name = True
    _attr_name = "Humidity"
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_device_class = SensorDeviceClass.HUMIDITY

    def __init__(self, coordinator: MadelonVentilationCoordinator) -> None:
        """Initialize the humidity sensor."""
        self._attr_unique_id = (
            f"{DOMAIN}_{coordinator.system.unique_identifier}_humidity"
        )
        super().__init__(coordinator)

    def _update_from_snapshot(self) -> None:
        self._attr_native_value = self._system.humidity


class FreshAirFilterUsageSensor(FreshAirSensorEntity):
    """Fresh Air System filter usage sensor."""

    _attr_has_entity_name = True
    _attr_name = "Filter Usage Time"
    _attr_native_unit_of_measurement = UnitOfTime.HOURS
    _attr_state_class = SensorStateClass.TOTAL_INCREASING
    _attr_icon = "mdi:air-filter"

    def __init__(self, coordinator: MadelonVentilationCoordinator) -> None:
        """Initialize the filter usage sensor."""
        self._attr_unique_id = (
            f"{DOMAIN}_{coordinator.system.unique_identifier}_filter_usage_time"
        )
        super().__init__(coordinator)

    def _update_from_snapshot(self) -> None:
        self._attr_native_value = self._system.filter_usage_time
