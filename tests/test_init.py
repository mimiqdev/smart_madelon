from unittest.mock import patch, MagicMock
from homeassistant.config_entries import ConfigEntryState
from custom_components.madelon_ventilation.const import DOMAIN
from pytest_homeassistant_custom_component.common import MockConfigEntry
import pytest


@pytest.mark.asyncio
async def test_setup_entry(hass):
    """Test setting up the entry."""
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
        mock_modbus.return_value.connect.return_value = True
        mock_modbus.return_value.connected = True

        # Mock register read for initial setup
        mock_response = MagicMock()
        mock_response.registers = [0] * 20
        mock_modbus.return_value.read_holding_registers.return_value = mock_response

        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state == ConfigEntryState.LOADED
    assert DOMAIN in hass.data
    assert entry.entry_id in hass.data[DOMAIN]
