from unittest.mock import patch, MagicMock
from homeassistant.helpers.entity_component import async_update_entity
from custom_components.madelon_ventilation.const import DOMAIN
from pytest_homeassistant_custom_component.common import MockConfigEntry
import pytest


@pytest.mark.asyncio
async def test_sensor_entities(hass):
    """Test sensor entities."""
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

        # Mock register read: temp=25.5 (255), hum=45.0 (450), filter=100
        registers = [0] * 20
        registers[16] = 255  # temperature
        registers[17] = 450  # humidity
        registers[1] = 100  # filter_usage_time
        mock_response = MagicMock()
        mock_response.registers = registers
        client.read_holding_registers.return_value = mock_response

        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        # Manually trigger update for all sensors
        for entity_id in [
            "sensor.fresh_air_system_temperature",
            "sensor.fresh_air_system_humidity",
            "sensor.fresh_air_system_filter_usage_time",
        ]:
            await async_update_entity(hass, entity_id)

        # Check temperature sensor
        temp_sensor = hass.states.get("sensor.fresh_air_system_temperature")
        assert temp_sensor is not None
        assert temp_sensor.state == "25.5"

        # Check humidity sensor
        hum_sensor = hass.states.get("sensor.fresh_air_system_humidity")
        assert hum_sensor is not None
        assert hum_sensor.state == "45.0"

        # Check filter usage sensor
        filter_sensor = hass.states.get("sensor.fresh_air_system_filter_usage_time")
        assert filter_sensor is not None
        assert filter_sensor.state == "100"

        # Unload the entry
        assert await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()
