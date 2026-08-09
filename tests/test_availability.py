"""Regression tests for coordinator-backed entity availability."""

# pyright: reportMissingImports=false

from unittest.mock import MagicMock, patch

import pytest
from pytest_homeassistant_custom_component.common import (  # pyright: ignore[reportMissingImports]
    MockConfigEntry,
)

from custom_components.madelon_ventilation.const import DOMAIN
from custom_components.madelon_ventilation.fresh_air_controller import FreshAirSystem

ENTITY_IDS = (
    "fan.fresh_air_system_supply_fan",
    "switch.fresh_air_system_bypass",
    "sensor.fresh_air_system_temperature",
    "button.fresh_air_system_reset_filter_usage",
)


def _registers(*, power=1, supply_speed=1, bypass=1, temperature=255):
    registers = [0] * 18
    registers[0] = power
    registers[7] = supply_speed
    registers[9] = bypass
    registers[16] = temperature
    return registers


def _response(registers):
    return MagicMock(registers=registers)


def _entry(hass):
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={"host": "127.0.0.1", "port": 8899, "unit_id": 1},
        entry_id="test_entry",
    )
    entry.add_to_hass(hass)
    return entry


@pytest.mark.asyncio
async def test_initial_setup_offline_creates_unavailable_entities(hass):
    """An offline gateway must not prevent setup or fabricate entity state."""
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
        client.read_holding_registers.return_value = None

        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        system = hass.data[DOMAIN][entry.entry_id]["system"]
        assert system.available is False
        assert client.read_holding_registers.call_count == 1
        for entity_id in ENTITY_IDS:
            state = hass.states.get(entity_id)
            assert state is not None
            assert state.state == "unavailable"

        assert await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()


@pytest.mark.asyncio
async def test_coordinator_failure_and_recovery_use_one_read_per_cycle(hass):
    """A failed shared refresh hides stale state and a later refresh recovers it."""
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

        entry_data = hass.data[DOMAIN][entry.entry_id]
        coordinator = entry_data["coordinator"]
        system = entry_data["system"]
        assert client.read_holding_registers.call_count == 1
        assert hass.states.get(ENTITY_IDS[0]).state == "on"
        assert hass.states.get(ENTITY_IDS[1]).state == "on"

        last_known_cache = system._registers_cache
        client.read_holding_registers.return_value = None
        await coordinator.async_refresh()
        await hass.async_block_till_done()

        assert client.read_holding_registers.call_count == 2
        assert system._registers_cache is last_known_cache
        assert coordinator.last_update_success is False
        for entity_id in ENTITY_IDS:
            assert hass.states.get(entity_id).state == "unavailable"

        client.read_holding_registers.return_value = _response(
            _registers(power=0, supply_speed=3, bypass=0, temperature=199)
        )
        await coordinator.async_refresh()
        await hass.async_block_till_done()

        assert client.read_holding_registers.call_count == 3
        assert coordinator.last_update_success is True
        assert hass.states.get(ENTITY_IDS[0]).state == "off"
        assert hass.states.get(ENTITY_IDS[1]).state == "off"
        assert hass.states.get(ENTITY_IDS[2]).state == "19.9"
        assert hass.states.get(ENTITY_IDS[3]).state != "unavailable"

        assert await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()


def test_failed_forced_refresh_does_not_revalidate_ttl_cache():
    """A fresh-by-time cache cannot recover availability after a failed read."""
    system = FreshAirSystem("127.0.0.1")
    system.modbus.read_registers = MagicMock(
        side_effect=[_response(_registers(temperature=255)), None, None]
    )

    assert system.refresh_registers(force_refresh=True) is True
    assert system.temperature == 25.5
    assert system.refresh_registers(force_refresh=True) is False
    assert system.available is False
    assert system.temperature is None
    assert system.modbus.read_registers.call_count == 3

    system.modbus.read_registers.return_value = _response(_registers(temperature=201))
    system.modbus.read_registers.side_effect = None
    assert system.temperature == 20.1
    assert system.available is True
