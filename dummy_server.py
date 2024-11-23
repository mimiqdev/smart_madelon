import asyncio
from pymodbus.server.async_io import StartAsyncTcpServer, ModbusTcpServer
from pymodbus.device import ModbusDeviceIdentification
from pymodbus.datastore import ModbusSequentialDataBlock
from pymodbus.datastore import ModbusSlaveContext, ModbusServerContext
import logging
import time

# Configure logging
logging.basicConfig()
log = logging.getLogger()
log.setLevel(logging.DEBUG)

class CustomSlaveContext(ModbusSlaveContext):
    """Custom slave context that updates actual values when control values change."""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._last_write_time = 0
    
    def setValues(self, fx, address, values):
        """Override setValues to implement custom logic with delay requirement."""
        current_time = time.time()
        time_since_last_write = (current_time - self._last_write_time) * 1000  # Convert to milliseconds
        
        if time_since_last_write < 200:
            log.warning(f"Write too fast! Must wait at least 200ms between writes. Only {time_since_last_write:.1f}ms has passed.")
            return  # Simply return without writing instead of raising an exception
        
        # Update last write time
        self._last_write_time = current_time
        
        # Proceed with the write
        super().setValues(fx, address, values)
        log.debug(f"Written value {values} to register {address}")
        
        # Map of control registers to actual registers
        CONTROL_TO_ACTUAL = {
            7: 12,  # supply_speed -> actual_supply
            8: 13   # exhaust_speed -> actual_exhaust
        }
        
        # If we're writing to a control register, update its corresponding actual register
        if address in CONTROL_TO_ACTUAL:
            actual_address = CONTROL_TO_ACTUAL[address]
            super().setValues(fx, actual_address, values)
            log.debug(f"Updated actual register {actual_address} with value {values}")

# Initialize data store
store = CustomSlaveContext(
    hr=ModbusSequentialDataBlock(0, [0]*100)  # 100 holding registers initialized to 0
)
context = ModbusServerContext(slaves=store, single=True)

# Server identity
identity = ModbusDeviceIdentification()
identity.VendorName = 'pymodbus'
identity.ProductCode = 'PM'
identity.VendorUrl = 'http://github.com/riptideio/pymodbus/'
identity.ProductName = 'pymodbus Server'
identity.ModelName = 'pymodbus Server'
identity.MajorMinorRevision = '1.0'

async def run_server():
    server = ModbusTcpServer(
        context=context,
        identity=identity,
        address=("localhost", 8899)
    )

    await server.serve_forever()

if __name__ == "__main__":
    asyncio.run(run_server())
