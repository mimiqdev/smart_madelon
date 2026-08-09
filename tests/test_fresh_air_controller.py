from concurrent.futures import ThreadPoolExecutor
from threading import Event
from unittest.mock import MagicMock, patch

import pytest

from custom_components.madelon_ventilation.fresh_air_controller import (
    FreshAirSystem,
    ModbusClient,
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


class FakeClock:
    def __init__(self):
        self.current = 0.0
        self.sleeps = []

    def monotonic(self):
        return self.current

    def sleep(self, seconds):
        self.sleeps.append(seconds)
        self.current += seconds


def test_modbus_client_enforces_interval_between_read_and_write(mock_modbus_client):
    client = ModbusClient("127.0.0.1")
    clock = FakeClock()
    mock_modbus_client.read_holding_registers.return_value = MagicMock(registers=[0])
    mock_modbus_client.write_register.return_value = MagicMock()

    with (
        patch(
            "custom_components.madelon_ventilation.fresh_air_controller.time.monotonic",
            side_effect=clock.monotonic,
        ),
        patch(
            "custom_components.madelon_ventilation.fresh_air_controller.time.sleep",
            side_effect=clock.sleep,
        ),
    ):
        assert client.read_registers(0, 1) is not None
        assert client.write_single_register(1, 1) is True

    assert clock.sleeps == pytest.approx([0.2])


def test_modbus_client_serializes_concurrent_requests(mock_modbus_client):
    client = ModbusClient("127.0.0.1")
    read_started = Event()
    finish_read = Event()
    write_started = Event()

    def blocking_read(**kwargs):
        read_started.set()
        finish_read.wait(timeout=1)
        return MagicMock(registers=[0])

    def tracked_write(**kwargs):
        write_started.set()
        return MagicMock()

    mock_modbus_client.read_holding_registers.side_effect = blocking_read
    mock_modbus_client.write_register.side_effect = tracked_write
    clock = FakeClock()

    with (
        patch(
            "custom_components.madelon_ventilation.fresh_air_controller.time.monotonic",
            side_effect=clock.monotonic,
        ),
        patch(
            "custom_components.madelon_ventilation.fresh_air_controller.time.sleep",
            side_effect=clock.sleep,
        ),
        ThreadPoolExecutor(max_workers=2) as executor,
    ):
        read_future = executor.submit(client.read_registers, 0, 1)
        assert read_started.wait(timeout=1)
        write_future = executor.submit(client.write_single_register, 1, 1)
        assert not write_started.wait(timeout=0.05)
        finish_read.set()
        assert read_future.result(timeout=1) is not None
        assert write_future.result(timeout=1) is True

    assert write_started.is_set()
    assert clock.sleeps == pytest.approx([0.2])


def test_reset_filter_usage_time_obeys_modbus_interval(mock_modbus_client):
    system = FreshAirSystem("127.0.0.1")
    clock = FakeClock()
    mock_modbus_client.write_register.return_value = MagicMock()
    mock_modbus_client.read_holding_registers.return_value = MagicMock(
        registers=[0] * 18
    )

    with (
        patch(
            "custom_components.madelon_ventilation.fresh_air_controller.time.monotonic",
            side_effect=clock.monotonic,
        ),
        patch(
            "custom_components.madelon_ventilation.fresh_air_controller.time.sleep",
            side_effect=clock.sleep,
        ),
    ):
        assert system.reset_filter_usage_time() is True

    assert clock.sleeps == pytest.approx([0.2])


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


def test_bypass_updates_cache_after_successful_write(mock_modbus_client):
    system = FreshAirSystem("127.0.0.1")
    system._registers_cache = [0] * 18
    system.modbus.write_single_register = MagicMock(return_value=True)

    system.bypass = True

    system.modbus.write_single_register.assert_called_once_with(9, 1)
    assert system._registers_cache[9] == 1


def test_bypass_preserves_cache_after_failed_write(mock_modbus_client):
    system = FreshAirSystem("127.0.0.1")
    system._registers_cache = [0] * 18
    system.modbus.write_single_register = MagicMock(return_value=False)

    system.bypass = True

    system.modbus.write_single_register.assert_called_once_with(9, 1)
    assert system._registers_cache[9] == 0


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
