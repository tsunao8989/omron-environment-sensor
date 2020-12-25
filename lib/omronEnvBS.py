# -*- coding: utf-8 -*-
from bluepy import btle
import time
import struct

def convert_dict(value, mode='EP'):
    data_dict = {}
    if mode == 'EP':
        (temp, humid, light, uv, press, noise, dcmf, wbgt, rfu, batt) = struct.unpack('<hhhhhhhhhB', bytes.fromhex(value[6:]))
        data_dict = {'d1': mode, 'd2': temp / 100, 'd3': humid / 100, 'd4': light,
                     'd5': uv / 100, 'd6': press / 10, 'd7': noise / 100, 'd8': (batt + 100) / 100}

    elif mode == 'IM':
        (temp, humid, light, uv, press, noise, accelX, accelY, accelZ, batt) = struct.unpack('<hhhhhhhhhB', bytes.fromhex(value[6:]))
        data_dict = {'d1': mode, 'd2': temp / 100, 'd3': humid / 100, 'd4': light,
                     'd5': uv / 100, 'd6': press / 10, 'd7':  noise / 100, 'd8': (batt + 100) / 100}
    
    return data_dict

class ScanDelegate(btle.DefaultDelegate):
    def __init__(self):
        btle.DefaultDelegate.__init__(self)
        self.dev_addr = None
        self.sensor_values = {}

    def handleDiscovery(self, dev, isNewDev, isNewData):
        if isNewDev or isNewData:  
            for (adtype, desc, value) in dev.getScanData():
                if desc == 'Manufacturer' and value[0:4] == 'd502':
                    # 検出した Bluetooth 端末の Macアドレスを取得
                    self.dev_addr = dev.addr
                    sensor_type = dev.scanData[dev.SHORT_LOCAL_NAME].decode(encoding='utf-8')
                    values = convert_dict(value, sensor_type)

                     # Macアドレスのキーが存在しない場合は dict を初期化
                    if self.dev_addr not in self.sensor_values.keys():
                        self.sensor_values[self.dev_addr] = {}

                    self.sensor_values[self.dev_addr] = values
