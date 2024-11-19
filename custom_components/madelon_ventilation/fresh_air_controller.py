from enum import Enum
from pymodbus.client import ModbusTcpClient
from pymodbus import (
    ExceptionResponse,
    ModbusException,
    # pymodbus_apply_logging_config,
)
import logging

# Enable logging
logging.basicConfig()
log = logging.getLogger()
log.setLevel(logging.WARNING)

class ModbusClient:
    def __init__(self, host, port, unit_id):
        self.client = ModbusTcpClient(host=host, port=port)
        self.unit_id = unit_id

    def read_registers(self, start_address, count):
        """Read multiple holding registers using FC03."""
        try:
            self.client.connect()
            response = self.client.read_holding_registers(start_address, count, unit=self.unit_id)
            if response.isError():
                print(f"Error reading registers: {response}")
                return None
            return response.registers
        finally:
            self.client.close()

    def write_single_register(self, address, value):
        """Write a single register using FC06."""
        try:
            self.client.connect()
            response = self.client.write_register(address, value, unit=self.unit_id)
            if response.isError():
                print(f"Error writing register: {response}")
        finally:
            self.client.close()

__all__ = ['FreshAirSystem', 'OperationMode']

class OperationMode(Enum):
    MANUAL = 0
    AUTO = 1
    TIMER = 2

class FreshAirSystem:
    """新风系统控制类"""
    
    # 寄存器地址映射
    REGISTERS = {
        'power': 0,        # Power mode: 0=off, 1=on
        'mode': 4,         # Mode: 0=manual, 1=auto, 2=timer
        'supply_speed': 7, # Supply speed: 1-3
        'exhaust_speed': 8,# Exhaust speed: 1-3
        'bypass': 9,       # Bypass: 0=off, 1=on
        'actual_supply': 12,# Actual supply speed
        'actual_exhaust': 13,# Actual exhaust speed
        'temperature': 16, # Temperature
        'humidity': 17,    # Humidity
    }

    def __init__(self, host, port, unit_id):
        self.modbus = ModbusClient(host=host, port=port, unit_id=unit_id)
        self._registers_cache = None
        self.unique_identifier = f"{host}:{port}:{unit_id}"  # Use host, port and unit_id as a unique identifier
        self.logger = logging.getLogger(__name__)
        self.logger.debug(f"Initialized FreshAirSystem with host: {host}, port: {port}, unit_id: {unit_id}")
        self.sensors = []  # List to hold sensor entities

    def register_sensor(self, sensor):
        """Register a sensor entity with the system."""
        self.sensors.append(sensor)

    def _read_all_registers(self):
        """一次性读取所有相关寄存器"""
        start_address = min(self.REGISTERS.values())
        count = max(self.REGISTERS.values()) - start_address + 1
        self.logger.debug(f"Reading all registers from {start_address} to {start_address + count - 1}")
        self._registers_cache = self.modbus.read_registers(start_address, count)
        self.logger.debug(f"Registers read: {self._registers_cache}")

        # Update all registered sensors
        for sensor in self.sensors:
            sensor.async_schedule_update_ha_state(True)

    def _get_register_value(self, name):
        """从缓存中获取寄存器值"""
        if self._registers_cache is None:
            self.logger.debug(f"Cache is empty, reading all registers for {name}")
            self._read_all_registers()
        address = self.REGISTERS[name]
        value = self._registers_cache[address] if self._registers_cache else None
        self.logger.debug(f"Register {name} (address {address}) value: {value}")
        return value

    def _validate_speed(self, speed):
        if not 1 <= speed <= 3:
            self.logger.error(f"Invalid speed: {speed}. Must be between 1 and 3.")
            raise ValueError("风速必须在1-3之间")
        self.logger.debug(f"Validated speed: {speed}")
        return speed

    @property
    def power(self):
        """获取电源状态"""
        return bool(self._get_register_value('power'))

    @power.setter
    def power(self, state: bool):
        """设置电源状态"""
        self.logger.debug(f"Setting power to: {state}")
        self.modbus.write_single_register(self.REGISTERS['power'], int(state))

    @property
    def mode(self):
        """获取运行模式"""
        return OperationMode(self._get_register_value('mode'))

    @mode.setter
    def mode(self, mode: OperationMode):
        """设置运行模式"""
        self.logger.debug(f"Setting mode to: {mode}")
        self.modbus.write_single_register(self.REGISTERS['mode'], mode.value)

    @property
    def supply_speed(self):
        """获取送风速度设置"""
        return self._get_register_value('actual_supply')

    @supply_speed.setter
    def supply_speed(self, speed: int):
        """设置送风速度"""
        self.logger.debug(f"Setting supply speed to: {speed}")
        self.modbus.write_single_register(self.REGISTERS['supply_speed'], 
                                        self._validate_speed(speed))

    @property
    def exhaust_speed(self):
        """获取排风速度设置"""
        return self._get_register_value('actual_exhaust')

    @exhaust_speed.setter
    def exhaust_speed(self, speed: int):
        """设置排风速度"""
        self.logger.debug(f"Setting exhaust speed to: {speed}")
        self.modbus.write_single_register(self.REGISTERS['exhaust_speed'], 
                                        self._validate_speed(speed))

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
    def temperature(self):
        """获取温度（°C）"""
        return self._get_register_value('temperature') / 10

    @property
    def humidity(self):
        """获取湿度（%）"""
        return self._get_register_value('humidity') / 10

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
