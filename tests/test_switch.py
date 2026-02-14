from unittest.mock import patch, MagicMock
from homeassistant.components.switch import (
    DOMAIN as SWITCH_DOMAIN,
    SERVICE_TURN_OFF,
)
from homeassistant.const import ATTR_ENTITY_ID
from custom_components.madelon_ventilation.const import DOMAIN
from pytest_homeassistant_custom_component.common import MockConfigEntry
import pytest


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

        # Test turn off bypass
        await hass.services.async_call(
            SWITCH_DOMAIN,
            SERVICE_TURN_OFF,
            {ATTR_ENTITY_ID: "switch.fresh_air_system_bypass"},
            blocking=True,
        )
        client.write_register.assert_called_with(address=9, value=0, device_id=1)

        # Unload the entry
        assert await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()
