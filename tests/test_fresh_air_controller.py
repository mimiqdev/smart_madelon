import pytest
from unittest.mock import MagicMock, patch
from custom_components.madelon_ventilation.fresh_air_controller import (
    FreshAirSystem,
    OperationMode,
)


@pytest.fixture
def mock_modbus_client():
    with patch(
        "custom_components.madelon_ventilation.fresh_air_controller.ModbusTcpClient"
    ) as mock:
        client_instance = mock.return_value
        client_instance.connected = True
        yield client_instance


def test_fresh_air_system_init(mock_modbus_client):
    system = FreshAirSystem("127.0.0.1")
    assert system.unique_identifier == "127.0.0.1:8899"


def test_fresh_air_system_power(mock_modbus_client):
    system = FreshAirSystem("127.0.0.1")

    # Mock read response
    mock_response = MagicMock()
    mock_response.registers = [1] + [0] * 20
    mock_modbus_client.read_holding_registers.return_value = mock_response

    assert system.power is True

    # Test setting power
    mock_modbus_client.write_register.return_value = True
    system.power = False
    mock_modbus_client.write_register.assert_called_with(
        address=0, value=0, device_id=1
    )
    assert system.power is False


def test_fresh_air_system_mode(mock_modbus_client):
    system = FreshAirSystem("127.0.0.1")

    # Mock read response for mode (address 4)
    # REGISTERS['mode'] = 4. min address is 0. So index is 4.
    registers = [0] * 20
    registers[4] = 1  # AUTO
    mock_response = MagicMock()
    mock_response.registers = registers
    mock_modbus_client.read_holding_registers.return_value = mock_response

    assert system.mode == OperationMode.AUTO

    # Test setting mode
    mock_modbus_client.write_register.return_value = True
    system.mode = OperationMode.MANUAL
    mock_modbus_client.write_register.assert_called_with(
        address=4, value=0, device_id=1
    )
    assert system.mode == OperationMode.MANUAL


def test_fresh_air_system_speed(mock_modbus_client):
    system = FreshAirSystem("127.0.0.1")

    # Mock read response for speeds (address 7 and 8)
    registers = [0] * 20
    registers[7] = 2  # medium
    registers[8] = 3  # high
    mock_response = MagicMock()
    mock_response.registers = registers
    mock_modbus_client.read_holding_registers.return_value = mock_response

    assert system.supply_speed == "medium"
    assert system.exhaust_speed == "high"

    # Test setting speed
    mock_modbus_client.write_register.return_value = True
    system.supply_speed = "high"
    mock_modbus_client.write_register.assert_called_with(
        address=7, value=3, device_id=1
    )
