"""Switch platform for Madelon Ventilation."""
from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.device_registry import DeviceInfo
from .const import DOMAIN
from .fresh_air_controller import FreshAirSystem, OperationMode
import logging

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback):
    """Set up the Madelon Ventilation switches."""
    system = hass.data[DOMAIN][entry.entry_id]["system"]
    
    # 首次读取所有寄存器数据到缓存
    _LOGGER.debug("Performing initial register read")
    success = await hass.async_add_executor_job(system._read_all_registers, True)
    _LOGGER.debug(f"Initial register read {'successful' if success else 'failed'}")
    
    if success:
        current_mode = system.mode
        _LOGGER.debug(f"Initial mode value: {current_mode}")
        
        # 创建开关并设置初始状态
        switches = [
            MadelonModeSwitch(system, "auto", OperationMode.AUTO, "Auto Mode"),
            MadelonModeSwitch(system, "manual", OperationMode.MANUAL, "Manual Mode"),
            MadelonModeSwitch(system, "timer", OperationMode.TIMER, "Timer Mode"),
            MadelonBypassSwitch(system),
        ]
        
        # 设置初始状态
        for switch in switches:
            if isinstance(switch, MadelonModeSwitch):
                if current_mode in [OperationMode.MANUAL, OperationMode.MANUAL_BYPASS] and switch._operation_mode == OperationMode.MANUAL:
                    switch._is_on = True
                elif current_mode in [OperationMode.AUTO, OperationMode.AUTO_BYPASS] and switch._operation_mode == OperationMode.AUTO:
                    switch._is_on = True
                elif current_mode in [OperationMode.TIMER, OperationMode.TIMER_BYPASS] and switch._operation_mode == OperationMode.TIMER:
                    switch._is_on = True
            elif isinstance(switch, MadelonBypassSwitch):
                switch._is_on = system.bypass

    async_add_entities(switches)


class MadelonModeSwitch(SwitchEntity):
    """Representation of a Madelon Ventilation mode switch."""

    def __init__(self, system: FreshAirSystem, mode_id: str, operation_mode: OperationMode, name: str):
        """Initialize the switch."""
        self._system = system
        self._mode_id = mode_id
        self._operation_mode = operation_mode
        self._attr_name = name
        self._attr_unique_id = f"{system.unique_identifier}_mode_{mode_id}"
        self._attr_has_entity_name = True
        self._is_on = False

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information about this entity."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._system.unique_identifier)},
            name="Fresh Air System",
            manufacturer="Madelon",
            model="XIXI",
            sw_version="1.0",
        )

    @property
    def is_on(self) -> bool:
        """Return true if switch is on."""
        return self._is_on

    def update(self) -> None:
        """Update the switch state."""
        try:
            # 直接从缓存中获取模式
            current_mode = self._system.mode
            _LOGGER.debug(f"Switch {self._attr_name} got current_mode: {current_mode}")
            
            if current_mode is None:
                self._is_on = False
                _LOGGER.debug(f"Switch {self._attr_name} setting is_on to False (mode is None)")
                return

            # 检查当前模式是否匹配此开关的模式
            old_state = self._is_on
            if self._operation_mode == OperationMode.MANUAL:
                self._is_on = current_mode in [OperationMode.MANUAL, OperationMode.MANUAL_BYPASS]
            elif self._operation_mode == OperationMode.AUTO:
                self._is_on = current_mode in [OperationMode.AUTO, OperationMode.AUTO_BYPASS]
            elif self._operation_mode == OperationMode.TIMER:
                self._is_on = current_mode in [OperationMode.TIMER, OperationMode.TIMER_BYPASS]
            
            if old_state != self._is_on:
                _LOGGER.debug(
                    f"Switch {self._attr_name} state changed from {old_state} to {self._is_on}"
                )
            
            _LOGGER.debug(
                f"Switch {self._attr_name} update complete: "
                f"current_mode={current_mode.value}, "
                f"operation_mode={self._operation_mode.value}, "
                f"is_on={self._is_on}"
            )
        except Exception as e:
            _LOGGER.error(f"Error updating switch {self._attr_name}: {e}", exc_info=True)

    def turn_on(self, **kwargs):
        """Turn the switch on."""
        try:
            current_mode = self._system.mode
            new_mode = self._operation_mode

            # 检查是否需要保持bypass状态
            if current_mode and '_bypass' in current_mode.value:
                new_mode = OperationMode.from_string(f"{self._operation_mode.value}_bypass")
            
            _LOGGER.debug(f"Switch {self._attr_name} turning on: setting mode to {new_mode.value}")
            
            # 获取寄存器地址和值
            register_address = self._system.REGISTERS['mode']
            register_value = self._system._convert_mode_string(new_mode)
            
            # 写入寄存器
            if self._system.modbus.write_single_register(register_address, register_value):
                # 写入成功后直接更新缓存
                self._system._update_cache_value('mode', register_value)
                self.update()
                # 通知其他相关实体更新状态
                for sensor in self._system.sensors:
                    sensor.schedule_update_ha_state(True)
            else:
                _LOGGER.error(f"Failed to set mode to {new_mode.value}")
                
        except Exception as e:
            _LOGGER.error(f"Error turning on switch {self._attr_name}: {e}", exc_info=True)

    def turn_off(self, **kwargs):
        """Turn the switch off."""
        try:
            if self._is_on:
                current_mode = self._system.mode
                new_mode = OperationMode.MANUAL

                # 保持bypass状态
                if current_mode and '_bypass' in current_mode.value:
                    new_mode = OperationMode.MANUAL_BYPASS

                _LOGGER.debug(f"Switch {self._attr_name} turning off: setting mode to {new_mode.value}")
                
                # 获取寄存器地址和值
                register_address = self._system.REGISTERS['mode']
                register_value = self._system._convert_mode_string(new_mode)
                
                # 写入寄存器
                if self._system.modbus.write_single_register(register_address, register_value):
                    # 写入成功后直接更新缓存
                    self._system._update_cache_value('mode', register_value)
                    self.update()
                    # 通知其他相关实体更新状态
                    for sensor in self._system.sensors:
                        sensor.schedule_update_ha_state(True)
                else:
                    _LOGGER.error(f"Failed to set mode to {new_mode.value}")
                    
        except Exception as e:
            _LOGGER.error(f"Error turning off switch {self._attr_name}: {e}", exc_info=True)


class MadelonBypassSwitch(SwitchEntity):
    """Representation of a Madelon Ventilation bypass switch."""

    def __init__(self, system: FreshAirSystem):
        """Initialize the bypass switch."""
        self._system = system
        self._attr_name = "Bypass Mode"
        self._attr_unique_id = f"{system.unique_identifier}_bypass"
        self._attr_has_entity_name = True
        self._is_on = False

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information about this entity."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._system.unique_identifier)},
            name="Fresh Air System",
            manufacturer="Madelon",
            model="XIXI",
            sw_version="1.0",
        )

    @property
    def is_on(self) -> bool:
        """Return true if bypass is on."""
        return self._is_on

    def update(self) -> None:
        """Update the bypass switch state."""
        try:
            # 直接从缓存中获取旁通状态
            bypass_state = self._system.bypass
            self._is_on = bool(bypass_state) if bypass_state is not None else False
            _LOGGER.debug(f"Bypass switch state updated: {self._is_on}")
        except Exception as e:
            _LOGGER.error(f"Error updating bypass switch state: {e}")
            self._is_on = False

    def turn_on(self, **kwargs):
        """Turn the bypass on."""
        try:
            # 直接写入旁通寄存器
            register_address = self._system.REGISTERS['bypass']
            if self._system.modbus.write_single_register(register_address, 1):
                self._system._update_cache_value('bypass', 1)
                self.update()
                # 通知其他相关实体更新状态
                for sensor in self._system.sensors:
                    sensor.schedule_update_ha_state(True)
            else:
                _LOGGER.error("Failed to turn on bypass")
        except Exception as e:
            _LOGGER.error(f"Error turning on bypass: {e}")

    def turn_off(self, **kwargs):
        """Turn the bypass off."""
        try:
            # 直接写入旁通寄存器
            register_address = self._system.REGISTERS['bypass']
            if self._system.modbus.write_single_register(register_address, 0):
                self._system._update_cache_value('bypass', 0)
                self.update()
                # 通知其他相关实体更新状态
                for sensor in self._system.sensors:
                    sensor.schedule_update_ha_state(True)
            else:
                _LOGGER.error("Failed to turn off bypass")
        except Exception as e:
            _LOGGER.error(f"Error turning off bypass: {e}")
