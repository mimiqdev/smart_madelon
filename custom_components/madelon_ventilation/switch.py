"""Switch platform for Madelon Ventilation."""

import logging

from homeassistant.components.switch import (  # pyright: ignore[reportMissingImports]
    SwitchEntity,
)
from homeassistant.config_entries import ConfigEntry  # pyright: ignore[reportMissingImports]
from homeassistant.core import HomeAssistant  # pyright: ignore[reportMissingImports]
from homeassistant.helpers.device_registry import (  # pyright: ignore[reportMissingImports]
    DeviceInfo,
)
from homeassistant.helpers.entity_platform import (  # pyright: ignore[reportMissingImports]
    AddEntitiesCallback,
)

from .const import (
    DEVICE_MANUFACTURER,
    DEVICE_MODEL,
    DEVICE_SW_VERSION,
    DOMAIN,
)
from .fresh_air_controller import FreshAirSystem, OperationMode

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
):
    """Set up the Madelon Ventilation switches."""
    system = hass.data[DOMAIN][entry.entry_id]["system"]

    # Read all registers
    _LOGGER.debug("Performing initial register read")
    success = await hass.async_add_executor_job(system._read_all_registers, True)
    _LOGGER.debug(f"Initial register read {'successful' if success else 'failed'}")

    # Create switches even if the device is temporarily unavailable.
    switches = [
        MadelonAutoModeSwitch(entry, system),
        MadelonBypassSwitch(entry, system),
    ]

    if success:
        current_mode = system.mode
        _LOGGER.debug(f"Initial mode value: {current_mode}")

        # Set initial states
        for switch in switches:
            if isinstance(switch, MadelonAutoModeSwitch):
                switch._is_on = current_mode == OperationMode.AUTO
            elif isinstance(switch, MadelonBypassSwitch):
                switch._is_on = system.bypass

    async_add_entities(switches)


class MadelonAutoModeSwitch(SwitchEntity):
    """Representation of a Madelon Ventilation auto/manual mode switch."""

    def __init__(self, entry: ConfigEntry, system: FreshAirSystem):
        """Initialize the switch."""
        self._system = system
        self._attr_name = "Auto Mode"
        self._attr_unique_id = f"{DOMAIN}_{system.unique_identifier}_auto_mode"
        self._attr_has_entity_name = True
        self._is_on = False

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

    @property
    def is_on(self) -> bool:
        """Return true if auto mode is on."""
        return self._is_on

    def update(self) -> None:
        """Update the switch state."""
        try:
            current_mode = self._system.mode
            _LOGGER.debug(f"Auto mode switch got current_mode: {current_mode}")

            if not self._system.available or current_mode is None:
                return

            # Auto mode is on when mode is AUTO, off when MANUAL
            self._is_on = current_mode == OperationMode.AUTO

            _LOGGER.debug(
                f"Auto mode switch update complete: "
                f"current_mode={current_mode.value}, "
                f"is_on={self._is_on}"
            )
        except Exception as e:
            _LOGGER.error(f"Error updating auto mode switch: {e}")

    def turn_on(self, **kwargs):
        """Turn on auto mode."""
        try:
            register_address = self._system.REGISTERS["mode"]
            register_value = self._system._convert_mode_string(OperationMode.AUTO)

            if self._system.modbus.write_single_register(
                register_address, register_value
            ):
                self._system._update_cache_value("mode", register_value)
                self.update()
                for sensor in self._system.sensors:
                    sensor.schedule_update_ha_state(True)
            else:
                _LOGGER.error("Failed to set auto mode")
        except Exception as e:
            _LOGGER.error(f"Error turning on auto mode: {e}")

    def turn_off(self, **kwargs):
        """Turn off auto mode (switch to manual mode)."""
        try:
            register_address = self._system.REGISTERS["mode"]
            register_value = self._system._convert_mode_string(OperationMode.MANUAL)

            if self._system.modbus.write_single_register(
                register_address, register_value
            ):
                self._system._update_cache_value("mode", register_value)
                self.update()
                for sensor in self._system.sensors:
                    sensor.schedule_update_ha_state(True)
            else:
                _LOGGER.error("Failed to set manual mode")
        except Exception as e:
            _LOGGER.error(f"Error turning off auto mode: {e}")


class MadelonBypassSwitch(SwitchEntity):
    """Representation of a Madelon Ventilation bypass switch."""

    def __init__(self, entry: ConfigEntry, system: FreshAirSystem):
        """Initialize the bypass switch."""
        self._system = system
        self._attr_name = "Bypass"
        self._attr_unique_id = f"{DOMAIN}_{system.unique_identifier}_bypass"
        self._attr_has_entity_name = True
        self._is_on = False

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

    @property
    def is_on(self) -> bool:
        """Return true if bypass is on."""
        return self._is_on

    def update(self) -> None:
        """Update the bypass switch state."""
        try:
            # Read bypass state from the system
            bypass_state = self._system.bypass
            if not self._system.available or bypass_state is None:
                return
            self._is_on = bool(bypass_state)
            _LOGGER.debug(f"Bypass switch state updated: {self._is_on}")
        except Exception as e:
            _LOGGER.error(f"Error updating bypass switch state: {e}")

    def turn_on(self, **kwargs):
        """Turn the bypass on."""
        try:
            # Write bypass state to the system
            register_address = self._system.REGISTERS["bypass"]
            if self._system.modbus.write_single_register(register_address, 1):
                self._system._update_cache_value("bypass", 1)
                self.update()
                # Notify other related entities to update their state
                for sensor in self._system.sensors:
                    sensor.schedule_update_ha_state(True)
            else:
                _LOGGER.error("Failed to turn on bypass")
        except Exception as e:
            _LOGGER.error(f"Error turning on bypass: {e}")

    def turn_off(self, **kwargs):
        """Turn the bypass off."""
        try:
            # Write bypass state to the system
            register_address = self._system.REGISTERS["bypass"]
            if self._system.modbus.write_single_register(register_address, 0):
                self._system._update_cache_value("bypass", 0)
                self.update()
                # Notify other related entities to update their state
                for sensor in self._system.sensors:
                    sensor.schedule_update_ha_state(True)
            else:
                _LOGGER.error("Failed to turn off bypass")
        except Exception as e:
            _LOGGER.error(f"Error turning off bypass: {e}")
