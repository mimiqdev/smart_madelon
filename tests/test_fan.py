# pyright: reportMissingImports=false

from unittest.mock import AsyncMock, MagicMock, call, patch

import pytest
from homeassistant.components.fan import (
    DOMAIN as FAN_DOMAIN,
)
from homeassistant.components.fan import (
    SERVICE_SET_PERCENTAGE,
    SERVICE_TURN_OFF,
)
from homeassistant.const import ATTR_ENTITY_ID
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.madelon_ventilation.const import DOMAIN
from custom_components.madelon_ventilation.fan import FreshAirFan


@pytest.mark.asyncio
async def test_fan_entities(hass):
    """Test fan entities."""
    config_data = {
        "host": "127.0.0.1",
        "port": 8899,
        "unit_id": 1,
    }

    entry = MockConfigEntry(
        domain=DOMAIN,
        data=config_data,
        entry_id="test_entry",
    )
    entry.add_to_hass(hass)

    with patch(
        "custom_components.madelon_ventilation.fresh_air_controller.ModbusTcpClient"
    ) as mock_modbus:
        client = mock_modbus.return_value
        client.connect.return_value = True
        client.connected = True

        # Mock register read: power=on (1), supply=low (1), exhaust=medium (2)
        registers = [0] * 20
        registers[0] = 1  # power
        registers[7] = 1  # supply_speed
        registers[8] = 2  # exhaust_speed
        mock_response = MagicMock()
        mock_response.registers = registers
        client.read_holding_registers.return_value = mock_response

        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        # Check supply fan
        supply_fan = hass.states.get("fan.fresh_air_system_supply_fan")
        assert supply_fan is not None
        assert supply_fan.state == "on"
        assert (
            supply_fan.attributes["percentage"] == 33
        )  # low in ["low", "medium", "high"]
        assert supply_fan.attributes["percentage_step"] == pytest.approx(100 / 3)

        # Check exhaust fan
        exhaust_fan = hass.states.get("fan.fresh_air_system_exhaust_fan")
        assert exhaust_fan is not None
        assert exhaust_fan.state == "on"
        assert exhaust_fan.attributes["percentage"] == 66  # medium
        assert exhaust_fan.attributes["percentage_step"] == pytest.approx(100 / 3)

        # Test turn off
        client.write_register.return_value = True
        await hass.services.async_call(
            FAN_DOMAIN,
            SERVICE_TURN_OFF,
            {ATTR_ENTITY_ID: "fan.fresh_air_system_supply_fan"},
            blocking=True,
        )
        client.write_register.assert_called_with(address=0, value=0, device_id=1)
        client.write_register.reset_mock()

        # The cached read was updated to off, so speed must precede power-on.
        await hass.services.async_call(
            FAN_DOMAIN,
            SERVICE_SET_PERCENTAGE,
            {ATTR_ENTITY_ID: "fan.fresh_air_system_supply_fan", "percentage": 100},
            blocking=True,
        )
        assert client.write_register.call_args_list == [
            call(address=7, value=3, device_id=1),
            call(address=0, value=1, device_id=1),
        ]

        # Unload the entry
        assert await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()


def _fan_for_write_test(hass, *, is_on: bool):
    system = MagicMock(unique_identifier="127.0.0.1:8899")
    coordinator = MagicMock(system=system, last_update_success=False)
    coordinator.async_request_refresh = AsyncMock()
    fan = FreshAirFan(coordinator, "supply")
    fan.hass = hass
    coordinator.last_update_success = True
    fan._attr_is_on = is_on
    return fan, system, coordinator


@pytest.mark.asyncio
async def test_percentage_writes_speed_before_power(hass):
    """A stopped fan receives its speed before the non-atomic power write."""
    fan, system, coordinator = _fan_for_write_test(hass, is_on=False)
    writes = []
    system.set_supply_speed.side_effect = lambda speed: (
        writes.append(("speed", speed)) or True
    )
    system.set_power.side_effect = lambda state: writes.append(("power", state)) or True

    await fan.async_set_percentage(100)

    assert writes == [("speed", "high"), ("power", True)]
    coordinator.async_request_refresh.assert_awaited_once_with()


@pytest.mark.asyncio
async def test_percentage_speed_failure_skips_power_and_refreshes(hass):
    """A failed speed selection must not power on, but state is reconciled."""
    fan, system, coordinator = _fan_for_write_test(hass, is_on=False)
    system.set_supply_speed.return_value = False

    await fan.async_set_percentage(66)

    system.set_supply_speed.assert_called_once_with("medium")
    system.set_power.assert_not_called()
    coordinator.async_request_refresh.assert_awaited_once_with()


@pytest.mark.asyncio
async def test_percentage_change_while_known_on_skips_power_write(hass):
    """Changing only speed does not rewrite known-on shared power state."""
    fan, system, coordinator = _fan_for_write_test(hass, is_on=True)
    system.set_supply_speed.return_value = True

    await fan.async_set_percentage(33)

    system.set_supply_speed.assert_called_once_with("low")
    system.set_power.assert_not_called()
    coordinator.async_request_refresh.assert_awaited_once_with()


def test_fans_have_three_discrete_speeds():
    """Test both fan types expose the three-speed FanEntity API."""
    system = MagicMock(unique_identifier="127.0.0.1:8899")
    coordinator = MagicMock(system=system, last_update_success=False)

    for fan_type in ("supply", "exhaust"):
        fan = FreshAirFan(coordinator, fan_type)

        assert fan.speed_count == 3
        assert fan.percentage_step == pytest.approx(100 / 3)
