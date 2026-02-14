from enum import Enum
from pymodbus.client import ModbusTcpClient
from pymodbus import (
    ExceptionResponse,
    # pymodbus_apply_logging_config,
)
import logging
from .const import DEFAULT_PORT, DEFAULT_UNIT_ID
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
        self.connection_timeout = 10  # 连接超时时间（秒）

    def _ensure_connected(self):
        """Ensure connection is established with retry mechanism"""
        start_time = time.time()
        for attempt in range(self.retry_count):
            try:
                if time.time() - start_time > self.connection_timeout:
                    self.logger.error("Connection timeout")
                    return False

                if self.client is None:
                    self.client = ModbusTcpClient(host=self.host, port=self.port)
                if not self.client.connected:
                    self.client.connect()
                return True
            except ConnectionRefusedError as e:
                self.logger.error(f"Connection refused: {e}")
            except TimeoutError as e:
                self.logger.error(f"Connection timeout: {e}")
            except ConnectionError as e:
                self.logger.error(f"Connection error: {e}")
            except Exception as e:
                self.logger.error(f"Unexpected error: {e}")
                raise

            if attempt < self.retry_count - 1:
                time.sleep(self.retry_delay)
        return False

    def read_registers(self, start_address, count):
        """Read multiple holding registers."""
        try:
            if not self._ensure_connected():
                return None
            response = self.client.read_holding_registers(
                address=start_address, count=count, device_id=self.unit_id
            )
            if isinstance(response, ExceptionResponse):
                self.logger.error(f"Error reading registers: {response}")
                return None
            return response
        except Exception as e:
            self.logger.error(f"Error reading registers: {e}")
            return None

    def write_single_register(self, address, value):
        """Write a single register."""
        try:
            if not self._ensure_connected():
                return False
            response = self.client.write_register(
                address=address, value=value, device_id=self.unit_id
            )
            if isinstance(response, ExceptionResponse):
                self.logger.error(f"Error writing register: {response}")
                return False
            return True
        except Exception as e:
            self.logger.error(f"Error writing register: {e}")
            return False

    def close(self):
        """显式关闭连接"""
        if self.client and self.client.connected:
            self.client.close()


__all__ = ["FreshAirSystem", "OperationMode"]


class OperationMode(Enum):
    MANUAL = "manual"
    AUTO = "auto"
    TIMER = "timer"

    @property
    def value(self) -> str:
        return self._value_

    @classmethod
    def from_string(cls, mode_str: str) -> "OperationMode":
        try:
            return cls(mode_str.lower())
        except ValueError:
            return cls.MANUAL


class FreshAirSystem:
    """新风系统控制类"""

    # 寄存器地址映射
    REGISTERS = {
        "power": 0,  # 电源控制
        "filter_usage_time": 1,  # 滤网使用时间（只读）
        "filter_reminder_setting": 2,  # 滤网使用时间提醒设置
        "filter_reminder": 3,  # 滤网提醒状态（只读）
        "mode": 4,  # 运行模式
        "supply_speed": 7,  # 送风速度设置
        "exhaust_speed": 8,  # 排风速度设置
        "bypass": 9,  # 旁通开关
        "actual_supply": 12,  # 实际送风速度
        "actual_exhaust": 13,  # 实际排风速度
        "temperature": 16,  # 温度
        "humidity": 17,  # 湿度
    }

    def __init__(self, host, port=DEFAULT_PORT, unit_id=DEFAULT_UNIT_ID):
        self.modbus = ModbusClient(host=host, port=port, unit_id=unit_id)
        self._registers_cache = None
        self.unique_identifier = (
            f"{host}:{port}"  # Use host and port as a unique identifier
        )
        self.logger = logging.getLogger(__name__)
        self.logger.debug(f"Initialized FreshAirSystem with host: {host}, port: {port}")
        self.sensors = []  # List to hold sensor entities
        self._cache_timestamp = None
        self._cache_ttl = 30  # 缓存有效期（秒）
        self._is_reading = False  # 添加读取锁

    def register_sensor(self, sensor):
        """Register a sensor entity with the system."""
        self.sensors.append(sensor)

    def _is_cache_valid(self):
        """检查缓存是否有效"""
        if self._cache_timestamp is None or self._registers_cache is None:
            return False
        return (time.time() - self._cache_timestamp) < self._cache_ttl

    def _read_all_registers(self, force_refresh=False):
        """一次性读取所有相关寄存器"""
        if not force_refresh and self._is_cache_valid():
            return True

        # 防止重复读取
        if self._is_reading:
            self.logger.debug("Already reading registers, skipping duplicate read")
            return True

        try:
            self._is_reading = True
            start_address = min(self.REGISTERS.values())
            count = max(self.REGISTERS.values()) - start_address + 1
            self.logger.debug(
                f"Reading all registers from {start_address} to {start_address + count - 1}"
            )
            response = self.modbus.read_registers(start_address, count)
            if response and hasattr(response, "registers"):
                self._registers_cache = response.registers
                self._cache_timestamp = time.time()
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
        finally:
            self._is_reading = False

    def _get_register_value(self, register_name):
        """获取寄存器值"""
        # Attempt to read/refresh registers if cache is invalid.
        # _read_all_registers() will only perform a read if the cache is stale or force_refresh is True.
        # We pass force_refresh=False to respect the cache TTL.
        self._read_all_registers(force_refresh=False)

        if self._registers_cache is None:
            self.logger.warning(
                f"Cannot get register value for '{register_name}': register cache is empty after attempting refresh."
            )
            return None

        try:
            register_address = self.REGISTERS[register_name]
            # The start_address for the cache array is the minimum address in REGISTERS
            start_address_in_cache = min(self.REGISTERS.values())
            # Calculate the index in the _registers_cache array
            index_in_cache = register_address - start_address_in_cache

            if 0 <= index_in_cache < len(self._registers_cache):
                return self._registers_cache[index_in_cache]
            else:
                self.logger.error(
                    f"Calculated index {index_in_cache} for register '{register_name}' is out of bounds "
                    f"for cache of size {len(self._registers_cache)}."
                )
                return None
        except KeyError:
            self.logger.error(
                f"Register name '{register_name}' not found in REGISTERS definition."
            )
            return None
        except Exception as e:  # Catch any other unexpected errors during cache access
            self.logger.error(
                f"Unexpected error retrieving '{register_name}' from cache: {e}"
            )
            return None

    def _validate_speed(self, speed):
        """Validate speed value (1-3)."""
        if not isinstance(speed, (int, str)):
            self.logger.error(f"Invalid speed type: {type(speed)}. Must be int or str.")
            raise ValueError("Speed must be an integer or string")

        # Convert string speeds to numbers
        speed_map = {"low": 1, "medium": 2, "high": 3}
        if isinstance(speed, str):
            if speed.lower() not in speed_map:
                self.logger.error(
                    f"Invalid speed string: {speed}. Must be 'low', 'medium', or 'high'."
                )
                raise ValueError("Invalid speed string")
            speed = speed_map[speed.lower()]

        if not 1 <= speed <= 3:
            self.logger.error(f"Invalid speed: {speed}. Must be between 1 and 3.")
            raise ValueError("Speed must be between 1-3")

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
        value = self._get_register_value("power")
        return bool(value) if value is not None else None

    @power.setter
    def power(self, state: bool):
        """设置电源状态"""
        self.logger.debug(f"Setting power to: {state}")
        result = self.modbus.write_single_register(self.REGISTERS["power"], int(state))
        if result:
            self._update_cache_value("power", int(state))

    @property
    def mode(self):
        """获取运行模式"""
        value = self._get_register_value("mode")
        self.logger.debug(f"Raw mode register value: {value}")
        if value is None:
            return None

        # 确保值在有效范围内
        if not 0 <= value <= 5:
            self.logger.warning(f"Invalid mode value: {value}, defaulting to MANUAL")
            return OperationMode.MANUAL

        converted_mode = self._convert_mode_value(value)
        self.logger.debug(
            f"Mode property returning: {converted_mode} (from value: {value})"
        )
        return converted_mode

    @mode.setter
    def mode(self, mode: OperationMode):
        """设置运行模式"""
        value = self._convert_mode_string(mode)
        self.logger.debug(f"Setting mode to: {mode.value} (register value: {value})")
        result = self.modbus.write_single_register(self.REGISTERS["mode"], value)
        if result:
            self._update_cache_value("mode", value)

    def _convert_mode_value(self, value: int) -> OperationMode:
        """Convert mode register value to OperationMode."""
        mode_map = {
            0: OperationMode.MANUAL,
            1: OperationMode.AUTO,
            2: OperationMode.TIMER,
        }
        return mode_map.get(value, OperationMode.MANUAL)

    def _convert_mode_string(self, mode: OperationMode) -> int:
        """Convert OperationMode to register value."""
        mode_map = {
            OperationMode.MANUAL: 0,
            OperationMode.AUTO: 1,
            OperationMode.TIMER: 2,
        }
        return mode_map.get(mode, 0)

    @property
    def supply_speed(self):
        """Get supply speed setting as string."""
        value = self._get_register_value("supply_speed")
        speed_map = {1: "low", 2: "medium", 3: "high"}
        return speed_map.get(value) if value is not None else None

    @supply_speed.setter
    def supply_speed(self, speed):
        """Set supply speed using either string or integer value."""
        validated_speed = self._validate_speed(speed)
        self.logger.debug(f"Setting supply speed to: {validated_speed}")
        result = self.modbus.write_single_register(
            self.REGISTERS["supply_speed"], validated_speed
        )
        if result:
            self._update_cache_value("supply_speed", validated_speed)

    @property
    def exhaust_speed(self):
        """Get exhaust speed setting as string."""
        value = self._get_register_value("exhaust_speed")
        speed_map = {1: "low", 2: "medium", 3: "high"}
        return speed_map.get(value) if value is not None else None

    @exhaust_speed.setter
    def exhaust_speed(self, speed):
        """Set exhaust speed using either string or integer value."""
        validated_speed = self._validate_speed(speed)
        self.logger.debug(f"Setting exhaust speed to: {validated_speed}")
        result = self.modbus.write_single_register(
            self.REGISTERS["exhaust_speed"], validated_speed
        )
        if result:
            self._update_cache_value("exhaust_speed", validated_speed)

    @property
    def bypass(self):
        """获取旁通状态"""
        return bool(self._get_register_value("bypass"))

    @bypass.setter
    def bypass(self, state: bool):
        """设置旁通状态"""
        self.logger.debug(f"Setting bypass to: {state}")
        self.modbus.write_single_register(self.REGISTERS["bypass"], int(state))

    @property
    def actual_supply_speed(self):
        """获取实际送风速度"""
        return self._get_register_value("actual_supply")

    @property
    def actual_exhaust_speed(self):
        """获取实际排风速度"""
        return self._get_register_value("actual_exhaust")

    @property
    def temperature(self):
        """获取温度（°C）"""
        value = self._get_register_value("temperature")
        return value / 10 if value is not None else None

    @property
    def humidity(self):
        """获取湿度（%）"""
        value = self._get_register_value("humidity")
        return value / 10 if value is not None else None

    @property
    def filter_usage_time(self):
        """获取滤网使用时间（小时）"""
        return self._get_register_value("filter_usage_time")

    @property
    def filter_reminder_setting(self):
        """获取滤网提醒设置时间（小时）"""
        return self._get_register_value("filter_reminder_setting")

    @filter_reminder_setting.setter
    def filter_reminder_setting(self, hours: int):
        """设置滤网提醒时间（小时）"""
        if not isinstance(hours, int) or not 0 <= hours <= 6000:
            self.logger.error(
                f"Invalid filter reminder setting: {hours}. Must be between 0-6000 hours."
            )
            raise ValueError("Filter reminder setting must be between 0-6000 hours")

        self.logger.debug(f"Setting filter reminder to: {hours} hours")
        result = self.modbus.write_single_register(
            self.REGISTERS["filter_reminder_setting"], hours
        )
        if result:
            self._update_cache_value("filter_reminder_setting", hours)

    @property
    def filter_reminder(self):
        """获取滤网提醒状态（0无提醒，1提醒）"""
        value = self._get_register_value("filter_reminder")
        return bool(value) if value is not None else None

    def reset_filter_usage_time(self):
        """重置滤网使用时间（写入1清除提醒）"""
        self.logger.debug("Resetting filter usage time")
        result = self.modbus.write_single_register(
            self.REGISTERS["filter_usage_time"], 1
        )
        if result:
            # 重置后，使用时间应该变为0
            self._update_cache_value("filter_usage_time", 0)
            # 强制刷新缓存以获取最新状态
            self._read_all_registers(force_refresh=True)
        return result


# 只在直接运行此文件时执行测试代码
if __name__ == "__main__":

    def test_fresh_air_system():
        host = "192.168.6.137"
        # host="127.0.0.1"
        system = FreshAirSystem(host, 8899, 1)

        # 读取所有状态
        print(f"电源状态: {system.power}")
        print(f"运行模式: {system.mode}")
        print(f"送风速度设置: {system.supply_speed}")
        print(f"排风速度设置: {system.exhaust_speed}")
        print(f"旁通状态: {system.bypass}")
        print(f"实际送风速度: {system.actual_supply_speed}")
        print(f"实际排风速度: {system.actual_exhaust_speed}")
        print(f"温度: {system.temperature}°C")
        print(f"湿度: {system.humidity}%")

        # system.power = True
        system.exhaust_speed = 1
        system.supply_speed = 1
        # print(f"电源状态: {system.power}")
        print(f"实际送风速度: {system.actual_supply_speed}")
        print(f"实际排风速度: {system.actual_exhaust_speed}")
        print(f"温度: {system.temperature}°C")
        print(f"湿度: {system.humidity}%")

    test_fresh_air_system()
