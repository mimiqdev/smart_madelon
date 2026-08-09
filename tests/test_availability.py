"""Regression tests for controller-backed entity availability."""

from unittest.mock import MagicMock, patch

import pytest
from homeassistant.helpers.entity_component import (  # pyright: ignore[reportMissingImports]
    async_update_entity,
)
from pytest_homeassistant_custom_component.common import (  # pyright: ignore[reportMissingImports]
    MockConfigEntry,
)

from custom_components.madelon_ventilation.button import FilterResetButton
from custom_components.madelon_ventilation.const import DOMAIN
from custom_components.madelon_ventilation.fan import FreshAirFan
from custom_components.madelon_ventilation.fresh_air_controller import FreshAirSystem
from custom_components.madelon_ventilation.sensor import FreshAirTemperatureSensor
from custom_components.madelon_ventilation.switch import MadelonBypassSwitch

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
        for entity_id in ENTITY_IDS:
            state = hass.states.get(entity_id)
            assert state is not None
            assert state.state == "unavailable"

        assert await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()


@pytest.mark.asyncio
async def test_entities_fail_and_recover_with_fresh_register_state(hass):
    """Failed reads hide stale state until a later real read succeeds."""
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

        system = hass.data[DOMAIN][entry.entry_id]["system"]
        assert system.available is True
        assert hass.states.get(ENTITY_IDS[0]).state == "on"
        assert hass.states.get(ENTITY_IDS[1]).state == "on"

        last_known_cache = system._registers_cache
        client.read_holding_registers.return_value = None
        assert (
            await hass.async_add_executor_job(system._read_all_registers, True) is False
        )
        assert system.available is False
        assert system._registers_cache is last_known_cache

        for entity_id in ENTITY_IDS:
            await async_update_entity(hass, entity_id)
        await hass.async_block_till_done()

        for entity_id in ENTITY_IDS:
            assert hass.states.get(entity_id).state == "unavailable"

        client.read_holding_registers.return_value = _response(
            _registers(power=0, supply_speed=3, bypass=0, temperature=199)
        )
        assert (
            await hass.async_add_executor_job(system._read_all_registers, True) is True
        )

        for entity_id in ENTITY_IDS:
            await async_update_entity(hass, entity_id)
        await hass.async_block_till_done()

        assert system.available is True
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

    assert system._read_all_registers(force_refresh=True) is True
    assert system.temperature == 25.5
    assert system._read_all_registers(force_refresh=True) is False
    assert system.available is False
    assert system.temperature is None
    assert system.modbus.read_registers.call_count == 3

    system.modbus.read_registers.return_value = _response(_registers(temperature=201))
    system.modbus.read_registers.side_effect = None
    assert system.temperature == 20.1
    assert system.available is True


def test_entity_updates_preserve_last_known_state_while_unavailable():
    """Communication failures do not overwrite entity last-known values."""
    system = MagicMock(unique_identifier="127.0.0.1:8899", available=True)
    system.power = True
    system.supply_speed = "medium"
    system.bypass = True
    system.temperature = 25.5

    fan = FreshAirFan(MagicMock(), system, "supply")
    bypass = MadelonBypassSwitch(MagicMock(), system)
    temperature = FreshAirTemperatureSensor(MagicMock(), system)
    button = FilterResetButton(MagicMock(), system)
    fan.update()
    bypass.update()
    temperature.update()

    system.available = False
    system.power = None
    system.supply_speed = None
    system.bypass = None
    system.temperature = None
    fan.update()
    bypass.update()
    temperature.update()

    assert fan.is_on is True
    assert fan.percentage == 66
    assert bypass.is_on is True
    assert temperature.native_value == 25.5
    assert fan.available is False
    assert bypass.available is False
    assert temperature.available is False
    assert button.available is False
    assert button.should_poll is True
