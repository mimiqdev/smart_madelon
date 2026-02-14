from unittest.mock import patch, MagicMock
from homeassistant.components.fan import (
    DOMAIN as FAN_DOMAIN,
    SERVICE_SET_PERCENTAGE,
    SERVICE_TURN_OFF,
)
from homeassistant.const import ATTR_ENTITY_ID
from custom_components.madelon_ventilation.const import DOMAIN
from pytest_homeassistant_custom_component.common import MockConfigEntry
import pytest


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

        # Check exhaust fan
        exhaust_fan = hass.states.get("fan.fresh_air_system_exhaust_fan")
        assert exhaust_fan is not None
        assert exhaust_fan.state == "on"
        assert exhaust_fan.attributes["percentage"] == 66  # medium

        # Test turn off
        client.write_register.return_value = True
        await hass.services.async_call(
            FAN_DOMAIN,
            SERVICE_TURN_OFF,
            {ATTR_ENTITY_ID: "fan.fresh_air_system_supply_fan"},
            blocking=True,
        )
        client.write_register.assert_called_with(address=0, value=0, device_id=1)

        # Test set percentage
        await hass.services.async_call(
            FAN_DOMAIN,
            SERVICE_SET_PERCENTAGE,
            {ATTR_ENTITY_ID: "fan.fresh_air_system_supply_fan", "percentage": 100},
            blocking=True,
        )
        # Power on first, then speed high (3)
        client.write_register.assert_any_call(address=0, value=1, device_id=1)
        client.write_register.assert_any_call(address=7, value=3, device_id=1)
