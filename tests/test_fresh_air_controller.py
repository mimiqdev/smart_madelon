from concurrent.futures import ThreadPoolExecutor
import subprocess
import sys
from threading import Event
from unittest.mock import MagicMock, patch

import pytest

import custom_components.madelon_ventilation.fresh_air_controller as controller_module
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


def test_import_does_not_configure_root_logger():
    script = """
import logging
root_logger = logging.getLogger()
handler = logging.NullHandler()
root_logger.handlers[:] = [handler]
root_logger.setLevel(logging.DEBUG)
import custom_components.madelon_ventilation.fresh_air_controller
assert root_logger.handlers == [handler]
assert root_logger.level == logging.DEBUG
"""
    subprocess.run([sys.executable, "-c", script], check=True)


def test_modbus_client_constructs_transport_with_explicit_timeout():
    transport = MagicMock(connected=False)
    transport.connect.return_value = False
    with patch.object(
        controller_module, "ModbusTcpClient", return_value=transport
    ) as tcp:
        client = controller_module.ModbusClient("127.0.0.1")
        client.retry_count = 1

        assert client._ensure_connected() is False

    tcp.assert_called_once_with(host="127.0.0.1", port=8899, timeout=1.0)


def test_connect_false_retries_without_real_waiting(mock_modbus_client):
    mock_modbus_client.connected = False
    mock_modbus_client.connect.return_value = False
    client = ModbusClient("127.0.0.1")
    clock = FakeClock()

    with (
        patch.object(controller_module.time, "monotonic", side_effect=clock.monotonic),
        patch.object(controller_module.time, "sleep", side_effect=clock.sleep),
    ):
        assert client._ensure_connected() is False

    assert mock_modbus_client.connect.call_count == 2
    assert clock.sleeps == pytest.approx([0.2])


def test_connection_retry_stops_when_budget_is_exhausted(mock_modbus_client):
    mock_modbus_client.connected = False
    clock = FakeClock()

    def consume_budget():
        clock.current += 2.5
        return False

    mock_modbus_client.connect.side_effect = consume_budget
    client = ModbusClient("127.0.0.1")

    with (
        patch.object(controller_module.time, "monotonic", side_effect=clock.monotonic),
        patch.object(controller_module.time, "sleep", side_effect=clock.sleep),
    ):
        assert client._ensure_connected() is False

    mock_modbus_client.connect.assert_called_once_with()
    assert clock.sleeps == []


def test_modbus_client_reconnects_after_idempotent_close():
    first_transport = MagicMock(connected=True)
    first_transport.read_holding_registers.return_value = MagicMock(registers=[1])
    second_transport = MagicMock(connected=True)
    second_transport.read_holding_registers.return_value = MagicMock(registers=[2])

    with patch.object(
        controller_module,
        "ModbusTcpClient",
        side_effect=[first_transport, second_transport],
    ) as tcp:
        client = controller_module.ModbusClient("127.0.0.1")
        first_response = client.read_registers(0, 1)
        assert first_response is not None
        assert first_response.registers == [1]
        client.close()
        client.close()
        second_response = client.read_registers(0, 1)
        assert second_response is not None
        assert second_response.registers == [2]

    assert tcp.call_count == 2
    first_transport.close.assert_called_once_with()
    second_transport.close.assert_not_called()


def test_modbus_client_rejects_modbus_error_responses(mock_modbus_client):
    client = ModbusClient("127.0.0.1")
    client.MIN_COMMUNICATION_INTERVAL = 0
    error_response = MagicMock()
    error_response.isError.return_value = True
    mock_modbus_client.read_holding_registers.return_value = error_response
    mock_modbus_client.write_register.return_value = error_response

    assert client.read_registers(0, 1) is None
    assert client.write_single_register(1, 1) is False


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
        assert system.refresh_registers(force_refresh=True) is True

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
