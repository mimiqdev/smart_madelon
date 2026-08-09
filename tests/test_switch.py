from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.components.switch import (  # pyright: ignore[reportMissingImports]
    DOMAIN as SWITCH_DOMAIN,
)
from homeassistant.components.switch import (  # pyright: ignore[reportMissingImports]
    SERVICE_TURN_OFF,
)
from homeassistant.const import ATTR_ENTITY_ID  # pyright: ignore[reportMissingImports]
from pytest_homeassistant_custom_component.common import (  # pyright: ignore[reportMissingImports]
    MockConfigEntry,
)

from custom_components.madelon_ventilation.const import DOMAIN
from custom_components.madelon_ventilation.switch import MadelonBypassSwitch


@pytest.mark.asyncio
async def test_switch_entities(hass):
    """Test switch entities."""
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

        # Mock register read: mode=AUTO (1), bypass=on (1)
        registers = [0] * 20
        registers[4] = 1  # mode AUTO
        registers[9] = 1  # bypass
        mock_response = MagicMock()
        mock_response.registers = registers
        client.read_holding_registers.return_value = mock_response

        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        # Check auto mode switch
        auto_switch = hass.states.get("switch.fresh_air_system_auto_mode")
        assert auto_switch is not None
        assert auto_switch.state == "on"

        # Check bypass switch
        bypass_switch = hass.states.get("switch.fresh_air_system_bypass")
        assert bypass_switch is not None
        assert bypass_switch.state == "on"

        # Test turn off auto mode (should set mode to MANUAL=0)
        client.write_register.return_value = True
        await hass.services.async_call(
            SWITCH_DOMAIN,
            SERVICE_TURN_OFF,
            {ATTR_ENTITY_ID: "switch.fresh_air_system_auto_mode"},
            blocking=True,
        )
        client.write_register.assert_called_with(address=4, value=0, device_id=1)
        assert hass.states.get("switch.fresh_air_system_auto_mode").state == "off"

        # Test turn off bypass
        await hass.services.async_call(
            SWITCH_DOMAIN,
            SERVICE_TURN_OFF,
            {ATTR_ENTITY_ID: "switch.fresh_air_system_bypass"},
            blocking=True,
        )
        client.write_register.assert_called_with(address=9, value=0, device_id=1)
        assert hass.states.get("switch.fresh_air_system_bypass").state == "off"

        # Unload the entry
        assert await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()


def _bypass_for_write_test(hass, *, is_on: bool):
    system = MagicMock(unique_identifier="127.0.0.1:8899")
    coordinator = MagicMock(system=system, last_update_success=False)
    coordinator.async_request_refresh = AsyncMock()
    bypass = MadelonBypassSwitch(coordinator)
    bypass.hass = hass
    bypass.async_write_ha_state = MagicMock()
    coordinator.last_update_success = True
    bypass._attr_is_on = is_on
    return bypass, system, coordinator


@pytest.mark.asyncio
async def test_switch_publishes_optimistic_state_before_modbus_io(hass):
    """The requested switch state is visible before the executor completes."""
    bypass, system, coordinator = _bypass_for_write_test(hass, is_on=True)
    system.set_bypass.return_value = True

    async def execute(write):
        assert not bypass.is_on
        bypass.async_write_ha_state.assert_called_once_with()
        return write()

    with patch.object(hass, "async_add_executor_job", side_effect=execute):
        await bypass.async_turn_off()

    coordinator.async_set_updated_data.assert_called_once_with(system)
    coordinator.async_request_refresh.assert_not_awaited()


@pytest.mark.asyncio
async def test_switch_rolls_back_optimistic_state_when_write_fails(hass):
    """A rejected switch write restores the previous UI state."""
    bypass, system, coordinator = _bypass_for_write_test(hass, is_on=True)
    system.set_bypass.return_value = False

    await bypass.async_turn_off()

    assert bypass.is_on
    assert bypass.async_write_ha_state.call_count == 2
    coordinator.async_set_updated_data.assert_not_called()
    coordinator.async_request_refresh.assert_awaited_once_with()


@pytest.mark.asyncio
async def test_switch_entities_created_when_initial_read_fails(hass):
    """Test switches are created while the device is temporarily offline."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={"host": "127.0.0.1", "port": 8899, "unit_id": 1},
        entry_id="test_entry",
    )
    entry.add_to_hass(hass)

    with patch(
        "custom_components.madelon_ventilation.fresh_air_controller."
        "FreshAirSystem.refresh_registers",
        return_value=False,
    ) as mock_initial_read:
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        mock_initial_read.assert_any_call(True)
        assert hass.states.get("switch.fresh_air_system_auto_mode") is not None
        assert hass.states.get("switch.fresh_air_system_bypass") is not None

        assert await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()
