from pythonosc import udp_client
from time import sleep
import test_cyberne_code_data
import csv
import struct
import nfc_structs
import binascii
num_blocks = 20
service_code = 0x090f
ADDRESS = '127.0.0.1'
PORT = 12000


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


def connected(tag):
    while True:
        print(tag)
        if isinstance(tag, nfc_structs.tag.tt3.Type3Tag):
            try:
                sc = nfc_structs.tag.tt3.ServiceCode(service_code >> 6, service_code & 0x3f)
                for i in range(num_blocks):
                    bc = nfc_structs.tag.tt3.BlockCode(i, service=0)
                    data = tag.read_without_encryption([sc], [bc])
                    history = HistoryRecord(bytes(data))
                    # if history.process is "運賃支払":
                    print(f"{i}")
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
                    print("".join(['%02x ' % s for s in data]))
                    idm = binascii.hexlify(tag.idm).decode()
                    sender_history(history.process, history.year, history.month, history.day,
                       history.in_station.station_value, history.in_line_key, history.in_station_key,
                       history.out_station.station_value, history.out_line_key, history.out_station_key)
                    if i == 19:
                        sleep(5)
            except Exception as e:
                print("error: %s" % e)
        else:
            print("error: tag isn't Type3Tag")


def sender_history(process, year, month, day,
                   in_station_value, in_line_key, in_station_key,
                   out_station_value, out_line_key, out_station_key):
    return process, year, month, day, \
           in_station_value, in_line_key, in_station_key, \
           out_station_value, out_line_key, out_station_key


def sender_idm():
    global idm
    print("Type3Tag0 ID=%s" % idm)
    return idm

# user_idの要素数をカウント
def count_all_logs():
    preserve_connection = sqlite3.connect(DATABASE_NAME)
    preserve_connection.row_factory = sqlite3.Row
    cursor = preserve_connection.cursor()
    query = '''
SELECT COUNT(all_logs.user_id = ? OR NULL) FROM all_logs
'''
    cursor.execute(query, [UserIdManager().user_id - 1])
    user_id_count = cursor
    preserve_connection.close()
    if user_id_count is None:
        return
    return user_id_count


def main_old():
    client = udp_client.SimpleUDPClient(ADDRESS, PORT, True)
    # sleep(1)
    # # TODO: NFC読み込み
    #
    # # TODO: NFC読み込み履歴をDBに保存
    #
    # # TODO: DBから履歴を読み込み
    #
    # # *** DBから緯度経度を検索 ***
    # # テストデータからランダムに取得
    # start_station, end_station = test_cyberne_code_data.get_cyberne_random_station_codes()
    # start_station_line_code = start_station[0]
    # start_station_code = start_station[1]
    # end_station_line_code = end_station[0]
    # end_station_code = end_station[1]
    # connection = sqlite3.connect(DATABASE_NAME)
    # connection.row_factory = sqlite3.Row
    # cursor = connection.cursor()
    # start_station = fetch_station_by_cyberne_code(cursor, start_station_line_code, start_station_code)
    # end_station = fetch_station_by_cyberne_code(cursor, end_station_line_code, end_station_code)
    # if start_station is None or end_station is None:
    #     return
    # start_station_name, start_station_lon, start_station_lat = start_station
    # end_station_name, end_station_lon, end_station_lat = end_station
    # print('start: ', start_station_name, start_station_lon, start_station_lat)
    # print('end: ', end_station_name, end_station_lon, end_station_lat)
    # connection.close()
    # # *** 緯度と経度を送信 ***
    # client.send_message('/line',
    #                     [start_station_name, start_station_lon, start_station_lat, end_station_name, end_station_lon,
    #                      end_station_lat])
    client.send_message('/action', [])


if __name__ == "__main__":
    clf = nfc_structs.ContactlessFrontend('usb')
    clf.connect(rdwr={'on-connect': connected})
