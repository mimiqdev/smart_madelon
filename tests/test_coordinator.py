"""Tests for shared DataUpdateCoordinator behavior."""

# pyright: reportMissingImports=false

from datetime import timedelta
import inspect
from unittest.mock import MagicMock, patch

import pytest
from homeassistant.const import CONF_SCAN_INTERVAL
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.madelon_ventilation.button import FilterResetButton
from custom_components.madelon_ventilation.const import (
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
)
from custom_components.madelon_ventilation.fan import FreshAirFan
from custom_components.madelon_ventilation.sensor import FreshAirTemperatureSensor
from custom_components.madelon_ventilation.switch import MadelonBypassSwitch


def _registers(*, power=1, supply_speed=1, bypass=1, temperature=255):
    registers = [0] * 18
    registers[0] = power
    registers[7] = supply_speed
    registers[9] = bypass
    registers[16] = temperature
    return registers


def _response(registers):
    return MagicMock(registers=registers)


def _entry(hass, *, options=None):
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={"host": "127.0.0.1", "port": 8899, "unit_id": 1},
        options=options or {},
        entry_id="test_entry",
    )
    entry.add_to_hass(hass)
    return entry


@pytest.mark.asyncio
async def test_all_platforms_share_one_batch_read_per_coordinator_cycle(hass):
    """Adding and notifying every platform does not duplicate the batch read."""
    entry = _entry(hass)

    with (
        patch(
            "custom_components.madelon_ventilation.fresh_air_controller."
            "ModbusClient.MIN_COMMUNICATION_INTERVAL",
            0,
        ),
        patch(
            "custom_components.madelon_ventilation.fresh_air_controller.ModbusTcpClient"
        ) as mock_modbus,
    ):
        client = mock_modbus.return_value
        client.connected = True
        client.read_holding_registers.return_value = _response(_registers())

        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        coordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]

        assert client.read_holding_registers.call_count == 1
        await coordinator.async_refresh()
        await hass.async_block_till_done()
        assert client.read_holding_registers.call_count == 2

        assert await hass.config_entries.async_unload(entry.entry_id)


def test_entities_use_coordinator_without_legacy_polling():
    """Every platform follows CoordinatorEntity and no fan timer remains."""
    coordinator = MagicMock(last_update_success=False)
    coordinator.system.unique_identifier = "127.0.0.1:8899"
    entities = (
        FreshAirFan(coordinator, "supply"),
        FreshAirTemperatureSensor(coordinator),
        MadelonBypassSwitch(coordinator),
        FilterResetButton(coordinator),
    )

    assert all(isinstance(entity, CoordinatorEntity) for entity in entities)
    assert all(not entity.should_poll for entity in entities)

    import custom_components.madelon_ventilation.fan as fan_platform

    source = inspect.getsource(fan_platform)
    assert "async_track_time_interval" not in source
    assert "def update(" not in source
    controller_source = inspect.getsource(
        __import__(
            "custom_components.madelon_ventilation.fresh_air_controller",
            fromlist=["fresh_air_controller"],
        )
    )
    assert "register_sensor" not in controller_source
    assert "schedule_update_ha_state" not in controller_source


@pytest.mark.parametrize(
    ("options", "expected_seconds"),
    [({}, DEFAULT_SCAN_INTERVAL), ({CONF_SCAN_INTERVAL: 42}, 42)],
)
@pytest.mark.asyncio
async def test_scan_interval_uses_default_or_configured_option(
    hass, options, expected_seconds
):
    """The coordinator interval comes from config-entry options with a default."""
    entry = _entry(hass, options=options)

    with patch(
        "custom_components.madelon_ventilation.fresh_air_controller.ModbusTcpClient"
    ) as mock_modbus:
        client = mock_modbus.return_value
        client.connected = True
        client.read_holding_registers.return_value = _response(_registers())

        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        coordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
        assert coordinator.update_interval == timedelta(seconds=expected_seconds)

        assert await hass.config_entries.async_unload(entry.entry_id)


@pytest.mark.asyncio
async def test_options_change_reloads_coordinator_interval(hass):
    """Changing options reloads the entry so a new interval takes effect."""
    entry = _entry(hass)

    with patch(
        "custom_components.madelon_ventilation.fresh_air_controller.ModbusTcpClient"
    ) as mock_modbus:
        client = mock_modbus.return_value
        client.connected = True
        client.read_holding_registers.return_value = _response(_registers())

        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        old_coordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]

        hass.config_entries.async_update_entry(entry, options={CONF_SCAN_INTERVAL: 25})
        await hass.async_block_till_done()

        new_coordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
        assert new_coordinator is not old_coordinator
        assert new_coordinator.update_interval == timedelta(seconds=25)

        assert await hass.config_entries.async_unload(entry.entry_id)


@pytest.mark.asyncio
async def test_successful_write_refreshes_related_state(hass):
    """A successful write requests one refresh and synchronizes related entities."""
    entry = _entry(hass)

    with (
        patch(
            "custom_components.madelon_ventilation.fresh_air_controller."
            "ModbusClient.MIN_COMMUNICATION_INTERVAL",
            0,
        ),
        patch(
            "custom_components.madelon_ventilation.fresh_air_controller.ModbusTcpClient"
        ) as mock_modbus,
    ):
        client = mock_modbus.return_value
        client.connected = True
        client.write_register.return_value = MagicMock()
        client.read_holding_registers.side_effect = [
            _response(_registers(bypass=1, temperature=255)),
            _response(_registers(bypass=0, temperature=201)),
        ]

        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        assert hass.states.get("switch.fresh_air_system_bypass").state == "on"
        assert hass.states.get("sensor.fresh_air_system_temperature").state == "25.5"

        await hass.services.async_call(
            "switch",
            "turn_off",
            {"entity_id": "switch.fresh_air_system_bypass"},
            blocking=True,
        )
        await hass.async_block_till_done()

        client.write_register.assert_called_once_with(address=9, value=0, device_id=1)
        assert client.read_holding_registers.call_count == 2
        assert hass.states.get("switch.fresh_air_system_bypass").state == "off"
        assert hass.states.get("sensor.fresh_air_system_temperature").state == "20.1"

        assert await hass.config_entries.async_unload(entry.entry_id)


@pytest.mark.asyncio
async def test_unload_closes_modbus_once(hass):
    """Normal unload closes the Modbus client exactly once."""
    entry = _entry(hass)

    with patch(
        "custom_components.madelon_ventilation.fresh_air_controller.ModbusTcpClient"
    ) as mock_modbus:
        client = mock_modbus.return_value
        client.connected = True
        client.read_holding_registers.return_value = _response(_registers())

        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        assert await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()

        client.close.assert_called_once_with()
        assert entry.entry_id not in hass.data[DOMAIN]
