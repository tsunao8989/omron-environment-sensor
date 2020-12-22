#!/usr/bin/env python
# -*- coding: utf-8 -*-

from bluepy import btle
from omronEnvBC import ScanDelegate

import requests
from urllib3.util import Retry
from requests.adapters import HTTPAdapter

import csv
import traceback
from argparse import ArgumentParser, RawDescriptionHelpFormatter
from datetime import datetime, timedelta

# ***********************************************************************
# For Logging
# ***********************************************************************
from logging import getLogger, StreamHandler, Formatter
from logging import DEBUG, ERROR, INFO

logger = getLogger(__name__)
handler = StreamHandler()
logger.addHandler(handler)
handler.setFormatter(Formatter('%(asctime)s %(levelname)7s %(message)s'))

# ***********************************************************************
# Default Setting
# ***********************************************************************
import configparser
import json
import os

config = configparser.ConfigParser()
configFile = '{}/{}'.format(os.path.dirname(os.path.abspath(__file__)), 'setting.ini')
config.read(configFile)

BLE_SCAN_TIME       = float(config.get('DEFAULT', 'BLE_SCAN_TIME')) # default 5.0
BLE_RETRY           = int(config.get('DEFAULT', 'BLE_RETRY')) # default 3
REQUEST_RETRY       = int(config.get('DEFAULT', 'REQUEST_RETRY'))  # default 3
REQUEST_FACTOR      = int(config.get('DEFAULT', 'REQUEST_FACTOR'))  # dafault 10
REQUEST_TIMEOUT     = json.loads(config.get('DEFAULT', 'REQUEST_TIMEOUT')) # default [10.0, 30.0]
REQUEST_FORCELIST   = json.loads(config.get('DEFAULT', 'REQUEST_FORCELIST')) # default [500, 502, 503, 504]
SPREADSHEET_URL     = config.get('GOOGLE_API', 'POST_URL')
OUTPUT_DIR          = config.get('DEFAULT', 'OUTPUT_DIR')
OUTPUT_FILENAME     = config.get('DEFAULT', 'OUTPUT_FILENAME')

# ***********************************************************************
# Return Values
# ***********************************************************************
REVAL_NORMAL        = 100
REVAL_NOTIFICATION  = 200
REVAL_WARNING       = 300
REVAL_ERROR         = 400
REVAL_CRITICAL      = 500

# ***********************************************************************
# Function
# ***********************************************************************
def bleScan(retry_count=BLE_RETRY, time=BLE_SCAN_TIME, devlists=[]):
    ''' BTLE のスキャン
    '''
    # omron_env_broadcast.py のセンサ値取得デリゲートを、スキャン時実行に設定
    scanner = btle.Scanner().withDelegate(ScanDelegate())
    try:
        # スキャンしてセンサ値取得
        logger.info('Start BTLE scanning ({})'.format(retry_count))
        scanner.scan(time)
    except Exception as e:
        logger.error('BTLE Exception while scannning. ({})'.format(e))
    
    values = scanner.delegate.sensorValues
    # デバイスが見つからない場合
    if len(values) == 0 and retry_count != 0:
        logger.info('Retry BTLE scanning. BTLE advertising data is not found. ')
        scanner = None
        return bleScan(retry_count=retry_count - 1)
    # 引数にリストが指定されている場合
    elif devlists and len(values) != 0:
        scanIDs = values.keys()
        # 対象センサーが見つからない場合はリトライ
        if set(scanIDs) != set(devlists) and retry_count != 0:
            logger.info('Retry BTLE scanning. DeviceId is not matched in list')
            scanner = None
            return bleScan(retry_count=retry_count - 1, devlists=devlists)
        elif retry_count == 0:
            logger.error("BTLE Scanning warning. Some data is missing.")
    elif retry_count == 0:
        logger.error("BTLE Scannning Failed. BTLE advertising data is not found.")
    # インスタンスの削除
    scanner = None
    logger.info('End BTLE scanning')
    return values

def _requests(url, method, *args, **kargs):
    ''' request の Wrapper
    '''
    method      = 'POST' if 'data' in kargs else method
    # requests.Session() のオプション
    retry_count = kargs['retry_count'] if 'retry_count' in kargs else REQUEST_RETRY
    timeout_val = kargs['timeout'] if 'timeout' in kargs else REQUEST_TIMEOUT 
    factor      = kargs['factor'] if 'factor' in kargs else REQUEST_FACTOR
    forcelists  = kargs['forcelist'] if 'forcelist' in kargs else REQUEST_FORCELIST   
    
    # forcelists の要素を int型に変更
    forcelist_array = [int(s) for s in forcelists]
    # timeout_val の要素を float型に変更し tuple の戻す
    timeout_array = [float(s) for s in timeout_val]
    timeout_tuple = tuple(timeout_array)
    
    session = requests.Session()
    # requests のリトライ設定
    retries = Retry(total=retry_count, backoff_factor=factor,
                    status_forcelist=forcelist_array)
    session.mount("https://", HTTPAdapter(max_retries=retries))
    session.mount("http://", HTTPAdapter(max_retries=retries))
    
    response = {}
    if method.upper() == 'POST':
        payload = kargs['data'] if 'data' in kargs else None
        try:
            logger.info('Start requests ({}) to ({})'
                        .format(method.upper(), url))
            response = session.post(
                url=url, data=payload, timeout=timeout_tuple)
        except Exception as e:
            logger.error('HTTP Exception ({})'.format(e))
            for trace_line in traceback.format_exc().rstrip().split('\n'):
                logger.error(trace_line)
    elif method.upper() == 'GET':
        header = kargs['header'] if 'header' in kargs else None
        param  = kargs['param'] if 'param' in kargs else None
        try:
            logger.info('Start requests ({}) from ({})'
                        .format(method.upper(), url))
            response = session.get(
                url=url, headers=header, params=param, timeout=timeout_tuple)
        except Exception as e:
            logger.error('HTTP Exception ({})'.format(e))
            for trace_line in traceback.format_exc().rstrip().split('\n'):
                logger.error(trace_line)
    
    logger.info('End request.')
    return response

def convert_array(values, mode='dict'):
    ''' データをアレイ形式に変換
    '''
    date = datetime.today()
    # 現時刻を分単位で丸める
    master_date = date.replace(second=0, microsecond=0)
    if date.second >= 30:
        master_date += timedelta(minutes=1)
    
    return_array = []
    if isinstance(values, dict) and len(values) != 0:
        if mode.lower() == 'dict':
            for key, value in values.items():
                dataset = {
                    'MacAddress':   str(key),
                    'Date_Master':  str(master_date),
                    'Date':         str(date),
                    'SensorType':   str(value['SensorType']),
                    'Temperature':  str(value['Temperature']),
                    'Humidity':     str(value['Humidity']),
                    'Light':        str(value['Light']),
                    'UV':           str(value['UV']),
                    'Pressure':     str(value['Pressure']),
                    'Noise':        str(value['Noise']),
                    'Batter':       str(value['BatteryVoltage'])
                }
                return_array.append(dataset)
        elif mode.lower() == 'list':
            for key, value in values.items():
                dataset = [
                    str(master_date),
                    str(date),
                    str(key),
                    str(value['SensorType']),
                    str(value['Temperature']),
                    str(value['Humidity']),
                    str(value['Light']),
                    str(value['UV']),
                    str(value['Pressure']),
                    str(value['Noise']),
                    str(value['BatteryVoltage'])
                ]
                return_array.append(dataset)

    return return_array

def post_spread_sheet(values,url=SPREADSHEET_URL):
    ''' Google スプレッドシートへ Post
    '''
    # NORMAL で初期値をセット
    result = REVAL_NORMAL
    method = 'POST'
    # センサーデータをアレイ形式に変換
    data_array = convert_array(values, mode='dict')
    if len(data_array) == 0:
        result = REVAL_ERROR
        logger.error('Data (data_array) is none. ')
        return result
    
    for data in data_array:
        response = _requests(url, method, data=data)
        if response.status_code != 200:
            result = REVAL_WARNING
            logger.error('Sending data to Google Spreadsheet failed.')

    return result

def write_csv_file(values, directory=OUTPUT_DIR, filename=OUTPUT_FILENAME, header=True):
    ''' CSV ファイルへの書き出し
    '''
    # NORMAL で初期値をセット
    result = REVAL_NORMAL
    output_data_array = []
    # センサーデータを CSV 出力用にアレイ形式に変換
    data_array = convert_array(values, mode='list')
    if len(data_array) == 0:
        result = REVAL_ERROR
        logger.error('Data (data_array) is none. ')
        return result

    # 保存先のディレクトリーがない場合は作成
    if not os.path.exists(directory):
        logger.info('Create ({}) .'.format(directory))
        os.makedirs(directory)
    target_file = '{}/{}'.format(directory, filename)

    # ファイルが存在しない場合,かつ header が True の場合はヘッダーを付与
    if not os.path.isfile(target_file) and header:
        output_data_array.append([
            'Date_Master',
            'Date',
            'MacAddress',
            'SensorType',
            'Temperature',
            'Humidity',
            'Light',
            'UV',
            'Pressure',
            'Noise',
            'BatteryVoltage'])
            
    output_data_array.extend(data_array)
    # ファイルの書き込み
    with open(target_file, 'a') as f:
        try:
            logger.info('writing csv file ({})'.format(target_file))
            writer = csv.writer(f, lineterminator='\n')
            writer.writerows(output_data_array)
            return result
        except Exception as e:
            logger.error('Write Csv Exception ({})'.format(e))
            for trace_line in traceback.format_exc().rstrip().split('\n'):
                logger.error(trace_line)
            result = REVAL_ERROR
            return result

# ***********************************************************************
# main
# ***********************************************************************    
def main():
    parser = ArgumentParser(description=(__doc__),
                            formatter_class=RawDescriptionHelpFormatter)
    parser.add_argument('-d', '--debug', action='store_true',
                        help='Outputting debug logs')
    parser.add_argument('-w', '--write', action='store_true',
                        help='Writing to csv file')

    args = parser.parse_args()
    if args.debug:
        logger.setLevel(DEBUG)
        handler.setLevel(DEBUG)
    
    #lists = ['f6:ae:2f:68:1a:b8', 'da:6f:c8:f0:23:0a']
    #lists = ['da:6f:c8:f0:23:0a']
    #d = {'f6:ae:2f:68:1a:b8': {'SensorType': 'EP', 'Temperature': 23.64, 'Humidity': 57.87, 'Light': 0, 'UV': 0.02, 'Pressure': 1016.5, 'Noise': 36.45, 'Discomfort': 70.71, 'WBGT': 21.02, 'BatteryVoltage': 2.72}, 'e6:5c:80:ae:0e:59': {'SensorType': 'EP', 'Temperature': 23.32, 'Humidity': 43.58, 'Light': 86, 'UV': 0.02, 'Pressure': 1015.9, 'Noise': 44.53, 'Discomfort': 69.01, 'WBGT': 18.96, 'BatteryVoltage': 2.92}}
    #d = {'DeviceName': 'f6:ae:2f:68:1a:b8', 'Date_Master': '2020-11-05 08:14:00', 'Date': '2020-11-05 08:14:13.281416', 'SensorType': 'EP', 'Temperature': '23.57', 'Humidity': '54.02', 'Light': '407', 'UV': '0.03', 'Pressure': '1020.8', 'Noise': '43.51', 'BatteryVoltage': '2.72'}
    omron_data = bleScan()
    if args.write:
        write_csv_file(omron_data)
    post_spread_sheet(omron_data)

if __name__ == "__main__":
    main()
