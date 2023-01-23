from time import sleep
from pythonosc import udp_client
import sqlite3
import binascii
# import nfc_structs
import test_cyberne_code_data
from config import DATABASE_NAME, num_blocks, service_code, ADDRESS, PORT
from managers.IdmManager import IdmManager
from managers.UserIdManager import UserIdManager
from nfc_structs.HistoryRecord import HistoryRecord
import nfc

user_id_manager = None
idm_manager = None


# ========================NFC==========================
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


def main(tag):
    print('connected:', binascii.hexlify(tag.idm).decode())
    # # TODO: NFC読み込み
    histories = read_nfc(tag)
    if histories is None:
        print('tag_error')
        send_error()
        return True
    idm = binascii.hexlify(tag.idm).decode()
    idm_manager.set_current(idm)
    # # TODO: NFC読み込み履歴をDBに保存
    is_sample = idm_manager.current_is_sample()
    # サンプルの時の処理
    if is_sample:
        send_histories(is_sample)
        print('サンプルだよ')
        return True

    # 通常時の処理
    # 新規の場合
    not_same_idm = idm_manager.check()
    if not_same_idm:
        save_history(histories)
        send_histories(is_sample)
        print('新規だよ')
    # 同じ場合
    else:
        send_histories(is_sample)
        print('同じだよ')
    return True


def read_nfc(tag) -> []:
    if not isinstance(tag, nfc.tag.tt3.Type3Tag):
        return None
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
    send_random_histories()


# ========================DB=========================
def save_history(histories):
    for history in histories:
        if history.process == "運賃支払":
            save_history_to_db(history.year, history.month, history.day,
                               history.in_station.station_value, history.in_line_key, history.in_station_key,
                               history.out_station.station_value, history.out_line_key, history.out_station_key)
    user_id_manager.up_count()


def save_history_to_db(year, month, day,
                       in_station_name, in_station_line_code, in_station_code,
                       out_station_name, out_station_line_code, out_station_code):
    query = '''
INSERT INTO all_logs values (?,?,?,?,?,?,?,?,?,?)
'''
    save_connection = sqlite3.connect(DATABASE_NAME)
    save_connection.row_factory = sqlite3.Row
    cursor = save_connection.cursor()
    cursor.execute(query,
                   [year, month, day, in_station_name, in_station_line_code, in_station_code,
                    out_station_name, out_station_line_code, out_station_code,
                    user_id_manager.user_id])
    save_connection.commit()
    save_connection.close()


# ========================OSC=========================
def send_histories(is_sample):
    client = udp_client.SimpleUDPClient(ADDRESS, PORT, True)
    if is_sample:
        histories_sample, histories_all = loading_history(is_sample)
        for history in histories_sample:
            client.send_message('/line_sample', history)
            print('sample送ったよ')
        for history in histories_all:
            client.send_message('/line_all', history)
            print('all送ったよ')
    else:
        histories_part, histories_all = loading_history(is_sample)
        for history in histories_part:
            client.send_message('/line_part', history)
            print('part送ったよ')
        for history in histories_all:
            client.send_message('/line_all', history)
            print('all送ったよ')
    client.send_message('/action', [])
    print('send_completed')


def loading_history(is_sample) -> []:
    aligned_histories = []
    if is_sample:
        query_sample = '''
SELECT * FROM all_logs
WHERE all_logs.user_id = ?
'''
        aligned_sample_histories = database_process(query_sample, is_sample)
        aligned_histories.append(aligned_sample_histories)

    else:
        query_part = '''
SELECT * FROM all_logs
WHERE all_logs.user_id = ?
'''
        aligned_part_histories = database_process(query_part, is_sample)
        aligned_histories.append(aligned_part_histories)

    query_all = '''
SELECT * FROM all_logs
WHERE all_logs.user_id != ?
'''
    is_sample = True
    aligned_all_histories = database_process(query_all, is_sample)
    aligned_histories.append(aligned_all_histories)
    return aligned_histories


def database_process(query, is_sample) -> []:
    process_connection = sqlite3.connect(DATABASE_NAME)
    process_connection.row_factory = sqlite3.Row
    cursor = process_connection.cursor()
    if is_sample:
        cursor.execute(query, [0])
    else:
        cursor.execute(query, [user_id_manager.user_id - 1])
    processed_histories = []
    for history in cursor:
        year = history['year']
        month = history['month']
        day = history['day']
        in_station_line_code = history['start_station_line_code']
        in_station_code = history['start_station_code']
        out_station_line_code = history['end_station_line_code']
        out_station_code = history['end_station_code']
        in_station_name, in_station_lon, in_station_lat = fetch_station_by_cyberne_code(cursor,
                                                                                        in_station_line_code,
                                                                                        in_station_code)
        out_station_name, out_station_lon, out_station_lat = fetch_station_by_cyberne_code(cursor,
                                                                                           out_station_line_code,
                                                                                           out_station_code)
        if in_station_name is not None or out_station_name is not None:
            processed_histories.append(
                [year, month, day,
                 in_station_name, in_station_lon, in_station_lat,
                 out_station_name, out_station_lon, out_station_lat])
    process_connection.close()
    return processed_histories


# ========================cyberne_code==========================
def fetch_station_by_cyberne_code(cursor, line_code, station_code):
    query = '''
SELECT stations.station_name, stations.lon, stations.lat
FROM cyberne_codes
JOIN stations on cyberne_codes.station_value = stations.station_name
WHERE stations.pref_cd = 13 AND
cyberne_codes.line_key = ? AND
cyberne_codes.station_key = ?
LIMIT 1;
'''
    cursor.execute(query, [line_code, station_code])
    station = cursor.fetchone()
    if station is None:
        return None, None, None
    station_name = station['station_name']
    station_lon = station['lon']
    station_lat = station['lat']
    return station_name, station_lon, station_lat


def send_random_histories():
    for i in range(10):
        sleep(0.1)
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
                            [start_station_name, start_station_lon, start_station_lat,
                             end_station_name, end_station_lon, end_station_lat])


def send_error():
    client = udp_client.SimpleUDPClient(ADDRESS, PORT, True)
    client.send_message('/error', [])


"""
oscで送るリスト
'/line_sample', [year, month, day,
                start_station_name, start_station_lon, start_station_lat,
                end_station_name, end_station_lon, end_station_lat]
'/line_part', 同様
'/line_all', 同様
'/line_random', [start_station_name, start_station_lon, start_station_lat, 
                end_station_name, end_station_lon, end_station_lat]
'/action', []
'/error', []
"""

if __name__ == '__main__':
    # send_random_histories()
    user_id_manager = UserIdManager(select_max() + 1)
    idm_manager = IdmManager()
    clf = nfc.ContactlessFrontend('usb')
    clf.connect(rdwr={'on-connect': main, 'on-release': released})
