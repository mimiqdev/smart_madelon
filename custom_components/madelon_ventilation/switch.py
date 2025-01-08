"""Switch platform for Madelon Ventilation."""
from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.device_registry import DeviceInfo
from .const import DOMAIN
from .fresh_air_controller import FreshAirSystem, OperationMode


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback):
    """Set up the Madelon Ventilation switches."""
    system = hass.data[DOMAIN][entry.entry_id]["system"]

    switches = [
        MadelonModeSwitch(system, "auto", OperationMode.AUTO, "Auto Mode"),
        MadelonModeSwitch(system, "manual", OperationMode.MANUAL, "Manual Mode"),
        MadelonModeSwitch(system, "timer", OperationMode.TIMER, "Timer Mode"),
    ]

    async_add_entities(switches)


class MadelonModeSwitch(SwitchEntity):
    """Representation of a Madelon Ventilation mode switch."""

    def __init__(self, system: FreshAirSystem, mode_id: str, operation_mode: OperationMode, name: str):
        """Initialize the switch."""
        self._system = system
        self._mode_id = mode_id
        self._operation_mode = operation_mode
        self._attr_name = name
        self._attr_unique_id = f"{system.unique_identifier}_mode_{mode_id}"
        self._attr_has_entity_name = True
        self._is_on = False

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

    @property
    def is_on(self) -> bool:
        """Return true if switch is on."""
        return self._is_on

    def update(self) -> None:
        """Update the switch state."""
        current_mode = self._system.mode
        self._is_on = current_mode == self._operation_mode.value if current_mode else False

    def turn_on(self, **kwargs):
        """Turn the switch on."""
        self._system.mode = self._operation_mode.value
        self.update()

    def turn_off(self, **kwargs):
        """Turn the switch off."""
        if self._is_on:
            self._system.mode = OperationMode.MANUAL.value
        self.update()
