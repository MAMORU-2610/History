

from time import sleep
from pythonosc import udp_client
import sqlite3
import binascii
import csv
import struct
import nfc

import test_cyberne_code_data

ADDRESS = '127.0.0.1'
PORT = 12000
DATABASE_NAME = './History.db'
num_blocks = 20
service_code = 0x090f
count = None
user_id_manager = None
idm_manager = None


# ========================NFC==========================
class StationRecord(object):
    db = None

    def __init__(self, row):
        self.area_key = int(row[0], 10)
        self.line_key = int(row[1], 10)
        self.station_key = int(row[2], 10)
        self.company_value = row[3]
        self.line_value = row[4]
        self.station_value = row[5]

    @classmethod
    # classmethodを書くことで、このメソッドのスタティック性を明示する
    def get_none(cls):
        # 駅データが見つからないときに使う
        return cls(["0", "0", "0", "None", "None", "None"])

    @classmethod
    def get_db(cls, filename):
        # 駅データのcsvを読み込んでキャッシュする
        if cls.db is None:
            cls.db = []
            for row in csv.reader(open(filename, 'rU'), delimiter=',', dialect=csv.excel_tab):
                cls.db.append(cls(row))
        return cls.db

    @classmethod
    def get_station(cls, line_key, station_key):
        # 線区コードと駅コードに対応するStationRecordを検索する
        for station in cls.get_db("CyberneCodes.csv"):
            if station.line_key == line_key and station.station_key == station_key:
                return station
        return cls.get_none()


class HistoryRecord(object):
    def __init__(self, data):
        # ビッグエンディアンでバイト列を解釈する
        row_be = struct.unpack('>2B2H4BH4B', data)
        # リトルエンディアンでバイト列を解釈する
        row_le = struct.unpack('<2B2H4BH4B', data)

        self.db = None
        self.console = self.get_console(row_be[0])
        self.process = self.get_process(row_be[1])
        self.year = self.get_year(row_be[3])
        self.month = self.get_month(row_be[3])
        self.day = self.get_day(row_be[3])
        self.balance = row_le[8]
        self.in_station = StationRecord.get_station(row_be[4], row_be[5])
        self.in_line_key = row_be[4]
        self.in_station_key = row_be[5]
        self.out_station = StationRecord.get_station(row_be[6], row_be[7])
        self.out_line_key = row_be[6]
        self.out_station_key = row_be[7]

    @classmethod
    def get_console(cls, key):
        # よく使われそうなもののみ対応
        return {
            0x03: "精算機",
            0x04: "携帯型端末",
            0x05: "車載端末",
            0x12: "券売機",
            0x16: "改札機",
            0x1c: "乗継精算機",
            0xc8: "自販機",
        }.get(key)

    @classmethod
    def get_process(cls, key):
        # よく使われそうなもののみ対応
        return {
            0x01: "運賃支払",
            0x02: "チャージ",
            0x0f: "バス",
            0x46: "物販",
        }.get(key)

    @classmethod
    def get_year(cls, date):
        return (date >> 9) & 0x7f

    @classmethod
    def get_month(cls, date):
        return (date >> 5) & 0x0f

    @classmethod
    def get_day(cls, date):
        return (date >> 0) & 0x1f


# ========================IDM--010104106b12e41d--==========================
class IdmManager:
    __sample_idm = '010104106b12e41d'

    def __init__(self):
        self.old = None
        self.current = None

    def set_current(self, current):
        self.old = self.current
        self.current = current

    def check(self) -> bool:
        """
        oldとcurrentが等しいか否かを返す
        :return:
        """
        return self.old != self.current

    def current_is_sample(self) -> bool:
        """
        currentがサンプルのIDMと一致しているか否かを返す
        :return:
        """
        return self.current == IdmManager.__sample_idm


# ========================USER_ID==========================
class UserIdManager:
    def __init__(self, start_id=0):
        self.user_id = start_id

    def count_up(self):
        self.user_id += 1


def select_max():
    query = '''
SELECT MAX(user_id) as max_user_id FROM all_logs
'''
    process_connection = sqlite3.connect(DATABASE_NAME)
    process_connection.row_factory = sqlite3.Row
    cursor = process_connection.cursor()
    cursor.execute(query)
    result = cursor.fetchone()
    return result['max_user_id']
# ========================NFC==========================
def main(tag):
    print('connected')
    print(binascii.hexlify(tag.idm).decode())
    # # TODO: NFC読み込み
    histories = nfc_reading(tag)
    idm = binascii.hexlify(tag.idm).decode()
    idm_manager.set_current(idm)
    # # TODO: NFC読み込み履歴をDBに保存
    is_sample = idm_manager.current_is_sample()
    if is_sample:
        print(' is_sample')
        return True
    else:
        print('not_sample')

    not_same = idm_manager.check()
    if not_same:
        print('not_same')
    else:
        print("not")
    # print(is_same)
    # サンプルの時の処理
    # if is_sample:
        # send_histories(is_sample)
        # return True

    # 通常時の処理
    # if idm_manager.check():
    # preserve_histories(histories)
        # send_histories(is_sample)
    return True


def nfc_reading(tag) -> []:
    if not isinstance(tag, nfc.tag.tt3.Type3Tag):
        return
    sc = nfc.tag.tt3.ServiceCode(service_code >> 6, service_code & 0x3f)
    histories = []
    for i in range(num_blocks):
        bc = nfc.tag.tt3.BlockCode(i, service=0)
        data = tag.read_without_encryption([sc], [bc])
        history = HistoryRecord(bytes(data))
        # print_history(history)
        histories.append(history)
    return histories


def print_history(history):
    print(f"端末種: {history.console}")
    print("処理: %s" % history.process)
    print("日付: %02d-%02d-%02d" % (history.year, history.month, history.day))
    print("入線区: %s-%s" % (history.in_station.company_value, history.in_station.line_value))
    print("入駅順: %s" % history.in_station.station_value)
    print("入駅コード: %s" % history.in_station_key)
    print("入路線コード: %s" % history.in_line_key)
    print("出線区: %s-%s" % (history.out_station.company_value, history.out_station.line_value))
    print("出駅順: %s" % history.out_station.station_value)
    print("出駅コード: %s" % history.out_station_key)
    print("出路線コード: %s" % history.out_line_key)
    print("残高: %d" % history.balance)
    print("BIN: ")


def released(tag):
    print('released')
    # client = udp_client.SimpleUDPClient(ADDRESS, PORT, True)
    # client.send_message('/action', [])


# ========================DB=========================
def preserve_histories(histories):
    for history in histories:
        if history.process == "運賃支払":
            preserve_to_db(history.year, history.month, history.day,
                           history.in_station.station_value, history.in_line_key, history.in_station_key,
                           history.out_station.station_value, history.out_line_key, history.out_station_key)
    user_id_manager.count_up()


def preserve_to_db(year, month, day,
                   start_station_name, start_station_line_code, start_station_code,
                   end_station_name, end_station_line_code, end_station_code):
    query = '''
INSERT INTO all_logs values (?,?,?,?,?,?,?,?,?,?)
'''
    preserve_connection = sqlite3.connect(DATABASE_NAME)
    preserve_connection.row_factory = sqlite3.Row
    cursor = preserve_connection.cursor()
    cursor.execute(query,
                   [year, month, day, start_station_name, start_station_line_code, start_station_code, end_station_name,
                    end_station_line_code, end_station_code, user_id_manager.user_id])
    preserve_connection.commit()
    preserve_connection.close()


# ========================OSC=========================
def send_histories(is_sample):
    client = udp_client.SimpleUDPClient(ADDRESS, PORT, True)
    if is_sample:
        histories_sample = loading_history(is_sample)
        for history in histories_sample:
            client.send_message('/line_sample', history)
    else:
        histories_part, histories_all = loading_history(is_sample)
        for history in histories_part:
            client.send_message('/line_part', history)
        for history in histories_all:
            client.send_message('/line_all', history)


def loading_history(is_sample) -> []:
    if is_sample:
        query_part = '''
SELECT * FROM all_logs
WHERE all_logs.user_id = ?
'''
        query_all = '''
SELECT * FROM all_logs
'''
        aligned_part_histories = process_database(query_part, is_sample)
        aligned_all_histories = process_database(query_all, is_sample)
        return aligned_part_histories, aligned_all_histories
    else:
        query_sample = '''
SELECT * FROM all_logs
WHERE all_logs.user_id = ?
'''
        aligned_sample_histories = process_database(query_sample, is_sample)
        return aligned_sample_histories


def process_database(query, is_sample) -> []:
    preserve_connection = sqlite3.connect(DATABASE_NAME)
    preserve_connection.row_factory = sqlite3.Row
    cursor = preserve_connection.cursor()
    if is_sample:
        # cursor.execute(query, [user_id_manager.user_id - 1])
        cursor.execute(query, [0])
    else:
        cursor.execute(query, [0])
    aligned_histories = []
    for history in cursor:
        year = history['year']
        month = history['month']
        day = history['day']
        start_station_line_code = history['start_station_line_code']
        start_station_code = history['start_station_code']
        end_station_line_code = history['end_station_line_code']
        end_station_code = history['end_station_code']
        start_station_name, start_station_lon, start_station_lat = fetch_station_by_cyberne_code(cursor,
                                                                                                 start_station_line_code,
                                                                                                 start_station_code)
        end_station_name, end_station_lon, end_station_lat = fetch_station_by_cyberne_code(cursor,
                                                                                           end_station_line_code,
                                                                                           end_station_code)
        aligned_histories.append(
            [year, month, day,
             start_station_name, start_station_lon, start_station_lat,
             end_station_name, end_station_lon, end_station_lat])
    preserve_connection.close()
    return aligned_histories


# ========================cyberne_code==========================
def fetch_station_by_cyberne_code(cursor, line_key, station_key):
    query = '''
SELECT stations.station_name, stations.lon, stations.lat
FROM cyberne_codes
JOIN stations on cyberne_codes.station_value = stations.station_name
WHERE stations.pref_cd = 13 AND
cyberne_codes.line_key = ? AND
cyberne_codes.station_key = ?
LIMIT 1;
'''
    cursor.execute(query, [line_key, station_key])
    station = cursor.fetchone()
    if station is None:
        return
    station_name = station['station_name']
    station_lon = station['lon']
    station_lat = station['lat']
    return station_name, station_lon, station_lat


def send_random_histories():
    while True:
        sleep(0.5)
        client = udp_client.SimpleUDPClient(ADDRESS, PORT, True)
        start_station, end_station = test_cyberne_code_data.get_cyberne_random_station_codes()
        start_station_line_code = start_station[0]
        start_station_code = start_station[1]
        end_station_line_code = end_station[0]
        end_station_code = end_station[1]
        connection = sqlite3.connect(DATABASE_NAME)
        connection.row_factory = sqlite3.Row
        cursor = connection.cursor()
        start_station = fetch_station_by_cyberne_code(cursor, start_station_line_code, start_station_code)
        end_station = fetch_station_by_cyberne_code(cursor, end_station_line_code, end_station_code)
        if start_station is None or end_station is None:
            return
        start_station_name, start_station_lon, start_station_lat = start_station
        end_station_name, end_station_lon, end_station_lat = end_station
        print('start: ', start_station_name, start_station_lon, start_station_lat)
        print('end: ', end_station_name, end_station_lon, end_station_lat)
        connection.close()
        client.send_message('/line_random',
                            [start_station_name, start_station_lon, start_station_lat, end_station_name, end_station_lon,
                             end_station_lat])


if __name__ == '__main__':
    # send_random_histories()
    user_id_manager = UserIdManager(select_max() + 1)
    idm_manager = IdmManager()
    clf = nfc.ContactlessFrontend('usb')
    clf.connect(rdwr={'on-connect': main, 'on-release': released})