from unittest.mock import patch, MagicMock
from homeassistant.components.button import (
    DOMAIN as BUTTON_DOMAIN,
    SERVICE_PRESS,
)
from homeassistant.const import ATTR_ENTITY_ID
from custom_components.madelon_ventilation.const import DOMAIN
from pytest_homeassistant_custom_component.common import MockConfigEntry
import pytest


@pytest.mark.asyncio
async def test_button_entities(hass):
    """Test button entities."""
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

        # Mock register read
        mock_response = MagicMock()
        mock_response.registers = [0] * 20
        client.read_holding_registers.return_value = mock_response

        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        # Check reset button
        reset_button = hass.states.get("button.fresh_air_system_reset_filter_usage")
        assert reset_button is not None

        # Test press button (should write 1 to address 1)
        client.write_register.return_value = True
        await hass.services.async_call(
            BUTTON_DOMAIN,
            SERVICE_PRESS,
            {ATTR_ENTITY_ID: "button.fresh_air_system_reset_filter_usage"},
            blocking=True,
        )
        client.write_register.assert_called_with(address=1, value=1, device_id=1)

        # Unload the entry
        assert await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()
