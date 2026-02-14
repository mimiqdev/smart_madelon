from unittest.mock import patch, MagicMock
from homeassistant import config_entries, data_entry_flow
from custom_components.madelon_ventilation.const import DOMAIN
import pytest


@pytest.mark.asyncio
async def test_config_flow_user(hass):
    """Test the user step of the config flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "user"

    with patch(
        "custom_components.madelon_ventilation.fresh_air_controller.ModbusTcpClient"
    ) as mock_modbus:
        mock_modbus.return_value.connect.return_value = True
        mock_modbus.return_value.connected = True
        mock_response = MagicMock()
        mock_response.registers = [0] * 20
        mock_modbus.return_value.read_holding_registers.return_value = mock_response

        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "host": "127.0.0.1",
                "port": 8899,
                "unit_id": 1,
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert result2["title"] == "Fresh Air System - 127.0.0.1"
    assert result2["data"] == {
        "host": "127.0.0.1",
        "port": 8899,
        "unit_id": 1,
    }


@pytest.mark.asyncio
async def test_config_flow_cannot_connect(hass):
    """Test failed connection in config flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "custom_components.madelon_ventilation.fresh_air_controller.ModbusTcpClient"
    ) as mock_modbus:
        mock_modbus.return_value.connect.return_value = False
        mock_modbus.return_value.connected = False
        mock_modbus.return_value.read_holding_registers.return_value = None

        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "host": "127.0.0.1",
                "port": 8899,
                "unit_id": 1,
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] == data_entry_flow.FlowResultType.FORM
    assert result2["errors"] == {"base": "cannot_connect"}
