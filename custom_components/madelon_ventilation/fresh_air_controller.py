from enum import Enum
from pymodbus.client import ModbusTcpClient
from pymodbus import (
    ExceptionResponse,
    ModbusException,
    # pymodbus_apply_logging_config,
)
import logging
from .const import DEFAULT_PORT, DEFAULT_UNIT_ID
import asyncio
import time

# Enable logging
logging.basicConfig()
log = logging.getLogger()
log.setLevel(logging.WARNING)


class ModbusClient:
    def __init__(self, host, port=DEFAULT_PORT, unit_id=DEFAULT_UNIT_ID):
        self.host = host
        self.port = port
        self.unit_id = unit_id
        self.client = None
        self.logger = logging.getLogger(__name__)
        self.retry_count = 3
        self.retry_delay = 1  # seconds

    def _ensure_connected(self):
        """Ensure connection is established with retry mechanism"""
        for attempt in range(self.retry_count):
            try:
                if self.client is None:
                    self.client = ModbusTcpClient(host=self.host, port=self.port)
                if not self.client.connected:
                    self.client.connect()
                return True
            except ConnectionError as e:
                self.logger.error(f"Connection attempt {attempt + 1} failed: {e}")
                if attempt < self.retry_count - 1:
                    time.sleep(self.retry_delay)
                continue
            except Exception as e:
                self.logger.error(f"Unexpected error: {e}")
                raise
        return False

    def read_registers(self, start_address, count):
        """Read multiple holding registers."""
        try:
            if not self._ensure_connected():
                return None
            response = self.client.read_holding_registers(
                address=start_address,
                count=count,
                slave=self.unit_id
            )
            if isinstance(response, ExceptionResponse):
                self.logger.error(f"Error reading registers: {response}")
                return None
            return response
        except Exception as e:
            self.logger.error(f"Error reading registers: {e}")
            return None
        finally:
            if self.client and self.client.connected:
                self.client.close()

    def write_single_register(self, address, value):
        """Write a single register."""
        try:
            if not self._ensure_connected():
                return False
            response = self.client.write_register(
                address=address,
                value=value,
                slave=self.unit_id
            )
            if isinstance(response, ExceptionResponse):
                self.logger.error(f"Error writing register: {response}")
                return False
            return True
        except Exception as e:
            self.logger.error(f"Error writing register: {e}")
            return False
        finally:
            if self.client and self.client.connected:
                self.client.close()


__all__ = ['FreshAirSystem', 'OperationMode']


class OperationMode(Enum):
    MANUAL = "manual"
    AUTO = "auto"
    TIMER = "timer"
    MANUAL_BYPASS = "manual_bypass"
    AUTO_BYPASS = "auto_bypass"
    TIMER_BYPASS = "timer_bypass"

    @property
    def value(self) -> str:
        return self._value_

    @classmethod
    def from_string(cls, mode_str: str) -> 'OperationMode':
        try:
            return cls(mode_str.lower())
        except ValueError:
            return cls.MANUAL


class FreshAirSystem:
    """新风系统控制类"""

    # 寄存器地址映射
    REGISTERS = {
        'power': 0,        # 电源控制
        'mode': 4,         # 运行模式
        'supply_speed': 7,  # 送风速度设置
        'exhaust_speed': 8,  # 排风速度设置
        'bypass': 9,       # 旁通开关
        'actual_supply': 12,  # 实际送风速度
        'actual_exhaust': 13,  # 实际排风速度
        'temperature': 16,  # 温度
        'humidity': 17,    # 湿度
    }

    def __init__(self, host, port=DEFAULT_PORT, unit_id=DEFAULT_UNIT_ID):
        self.modbus = ModbusClient(host=host, port=port, unit_id=unit_id)
        self._registers_cache = None
        self.unique_identifier = f"{host}:{port}"  # Use host and port as a unique identifier
        self.logger = logging.getLogger(__name__)
        self.logger.debug(f"Initialized FreshAirSystem with host: {host}, port: {port}")
        self.sensors = []  # List to hold sensor entities

    def register_sensor(self, sensor):
        """Register a sensor entity with the system."""
        self.sensors.append(sensor)

    def _read_all_registers(self):
        """一次性读取所有相关寄存器"""
        try:
            start_address = min(self.REGISTERS.values())
            count = max(self.REGISTERS.values()) - start_address + 1
            self.logger.debug(f"Reading all registers from {start_address} to {start_address + count - 1}")
            response = self.modbus.read_registers(start_address, count)
            if response and hasattr(response, 'registers'):
                self._registers_cache = response.registers
                self.logger.debug(f"Registers read: {self._registers_cache}")

                # Update all registered sensors
                for sensor in self.sensors:
                    sensor.schedule_update_ha_state(True)
                return True
            return False
        except Exception as e:
            self.logger.error(f"Error reading registers: {e}")
            self._registers_cache = None
            return False

    def _get_register_value(self, register_name):
        """获取寄存器值"""
        if self._registers_cache is None:
            if not self._read_all_registers():
                return None

        if self._registers_cache is None:
            return None

        register_address = self.REGISTERS[register_name]
        start_address = min(self.REGISTERS.values())
        return self._registers_cache[register_address - start_address]

    def _validate_speed(self, speed):
        if not 1 <= speed <= 3:
            self.logger.error(f"Invalid speed: {speed}. Must be between 1 and 3.")
            raise ValueError("风速必须在1-3之间")
        self.logger.debug(f"Validated speed: {speed}")
        return speed

    def _update_cache_value(self, register_name, value):
        """更新缓存中的值"""
        if self._registers_cache is not None:
            register_address = self.REGISTERS[register_name]
            start_address = min(self.REGISTERS.values())
            self._registers_cache[register_address - start_address] = value
            self.logger.debug(f"Updated cache for {register_name}: {value}")

    @property
    def power(self):
        """获取电源状态"""
        value = self._get_register_value('power')
        return bool(value) if value is not None else None

    @power.setter
    def power(self, state: bool):
        """设置电源状态"""
        self.logger.debug(f"Setting power to: {state}")
        result = self.modbus.write_single_register(self.REGISTERS['power'], int(state))
        if result:
            self._update_cache_value('power', int(state))

    @property
    def mode(self):
        """获取运行模式"""
        value = self._get_register_value('mode')
        return self._convert_mode_value(value) if value is not None else None

    @mode.setter
    def mode(self, mode: str):
        """设置运行模式"""
        value = self._convert_mode_string(mode)
        self.logger.debug(f"Setting mode to: {mode} (value: {value})")
        result = self.modbus.write_single_register(self.REGISTERS['mode'], value)
        if result:
            self._update_cache_value('mode', value)

    def _convert_mode_value(self, value: int) -> OperationMode:
        """Convert mode register value to OperationMode."""
        mode_map = {
            0: OperationMode.MANUAL,
            1: OperationMode.AUTO,
            2: OperationMode.TIMER,
            3: OperationMode.MANUAL_BYPASS,
            4: OperationMode.AUTO_BYPASS,
            5: OperationMode.TIMER_BYPASS
        }
        return mode_map.get(value, OperationMode.MANUAL)

    def _convert_mode_string(self, mode: OperationMode) -> int:
        """Convert OperationMode to register value."""
        mode_map = {
            OperationMode.MANUAL: 0,
            OperationMode.AUTO: 1,
            OperationMode.TIMER: 2,
            OperationMode.MANUAL_BYPASS: 3,
            OperationMode.AUTO_BYPASS: 4,
            OperationMode.TIMER_BYPASS: 5
        }
        return mode_map.get(mode, 0)

    @property
    def supply_speed(self):
        """获取送风速度设置"""
        return self._get_register_value('supply_speed')

    @supply_speed.setter
    def supply_speed(self, speed: int):
        """设置送风速度"""
        validated_speed = self._validate_speed(speed)
        self.logger.debug(f"Setting supply speed to: {validated_speed}")
        result = self.modbus.write_single_register(
            self.REGISTERS['supply_speed'],
            validated_speed
        )
        if result:
            self._update_cache_value('supply_speed', validated_speed)

    @property
    def exhaust_speed(self):
        """获取排风速度设置"""
        return self._get_register_value('exhaust_speed')

    @exhaust_speed.setter
    def exhaust_speed(self, speed: int):
        """设置排风速度"""
        validated_speed = self._validate_speed(speed)
        self.logger.debug(f"Setting exhaust speed to: {validated_speed}")
        result = self.modbus.write_single_register(
            self.REGISTERS['exhaust_speed'],
            validated_speed
        )
        if result:
            self._update_cache_value('exhaust_speed', validated_speed)

    @property
    def bypass(self):
        """获取旁通状态"""
        return bool(self._get_register_value('bypass'))

    @bypass.setter
    def bypass(self, state: bool):
        """设置旁通状态"""
        self.logger.debug(f"Setting bypass to: {state}")
        self.modbus.write_single_register(self.REGISTERS['bypass'], int(state))

    @property
    def actual_supply_speed(self):
        """获取实际送风速度"""
        return self._get_register_value('actual_supply')

    @property
    def actual_exhaust_speed(self):
        """获取实际排风速度"""
        return self._get_register_value('actual_exhaust')

    @property
    def temperature(self):
        """获取温度（°C）"""
        value = self._get_register_value('temperature')
        return value / 10 if value is not None else None

    @property
    def humidity(self):
        """获取湿度（%）"""
        value = self._get_register_value('humidity')
        return value / 10 if value is not None else None


# 只在直接运行此文件时执行测试代码
if __name__ == "__main__":
    def test_fresh_air_system():
        host = "192.168.6.137"
        # host="127.0.0.1"
        system = FreshAirSystem(host)

        # 读取所有状态
        # print(f"电源状态: {system.power}")
        # print(f"运行模式: {system.mode}")
        # print(f"送风速度设置: {system.supply_speed}")
        # print(f"排风速度设置: {system.exhaust_speed}")
        # print(f"旁通状态: {system.bypass}")
        # print(f"实际送风速度: {system.actual_supply_speed}")
        # print(f"实际排风速度: {system.actual_exhaust_speed}")
        # print(f"温度: {system.temperature}°C")
        # print(f"湿度: {system.humidity}%")

        system.power = False
        print(f"电源状态: {system.power}")

    test_fresh_air_system()
