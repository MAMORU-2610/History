from time import sleep
from pythonosc import udp_client
import sqlite3
import binascii
import nfc

from config import DATABASE_NAME, num_blocks, service_code
from managers.IdmManager import IdmManager
from managers.UserIdManager import UserIdManager
from managers.select_max import select_max
from managers.ClientManager import ClientManager
from nfc_structs.HistoryRecord import HistoryRecord
import test_cyberne_code_data

user_id_manager = None
idm_manager = None


# ========================NFC==========================
def main(tag):
    # nfc読み込み
    histories = read_nfc(tag)
    # タグが異なる時
    if histories is None:
        print('tag_error')
        send_error()
        return True

    print('connected:', binascii.hexlify(tag.idm).decode())
    idm = binascii.hexlify(tag.idm).decode()
    idm_manager.set_current(idm)
    is_sample = idm_manager.current_is_sample()
    # サンプルの時の処理
    if is_sample:
        print('サンプルだよ')
        send_sample_histories()
        return True

    # 通常時の処理
    # 新規の場合
    not_same_idm = idm_manager.check()
    if not_same_idm:
        print('新規だよ')
        save_history(histories)
        send_part_histories()
    # 同じ場合
    else:
        print('同じだよ')
        send_part_histories()
    return True


def read_nfc(tag) -> []:
    # if isinstance(tag, nfc.tag.tt4.Type4Tag):
    #     return None
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


def released(tag):
    print('released')
    is_sample = idm_manager.current_is_sample()
    if is_sample:
        print('------------send_completed:sample', '------------')
    else:
        print('------------send_completed:No.', user_id_manager.user_id - 1, '------------')


# ========================SAVE=========================
def save_history(histories):
    for history in histories:
        if history.process == "運賃支払":
            save_history_to_db(history.year, history.month, history.day,
                               history.in_station.station_value, history.in_line_key, history.in_station_key,
                               history.out_station.station_value, history.out_line_key, history.out_station_key)
    print('保存したよ')
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


# ========================SEND=========================
def send_sample_histories():
    histories_sample = loading_sample_history()
    for history in histories_sample:
        client_manager.client_point.send_message('/line_sample', history)
        client_manager.client_between.send_message('/line_sample', history)
        client_manager.client_particle.send_message('/line_sample', history)
    print('sample送ったよ')
    send_all_histories()
    send_random_histories()
    send_action()


def send_part_histories():
    histories_part = loading_part_history()
    for history in histories_part:
        client_manager.client_point.send_message('/line_part', history)
        client_manager.client_between.send_message('/line_part', history)
        client_manager.client_particle.send_message('/line_part', history)
    print('part送ったよ')
    send_all_histories()
    send_random_histories()
    send_action()


def send_all_histories():
    histories_all = loading_all_history()
    for history in histories_all:
        client_manager.client_point.send_message('/line_all', history)
        client_manager.client_between.send_message('/line_all', history)
        client_manager.client_particle.send_message('/line_all', history)
    print('all送ったよ')


def send_action():
    client_manager.client_opening.send_message('/action', [])
    client_manager.client_point.send_message('/action', [])
    client_manager.client_between.send_message('/action', [])
    client_manager.client_particle.send_message('/action', [])
    print('action送ったよ')


def send_error():
    client_manager.client_opening.send_message('/error', [])
    client_manager.client_point.send_message('/error', [])
    client_manager.client_between.send_message('/error', [])
    client_manager.client_particle.send_message('/error', [])
    print('error送ったよ')


# ========================LOAD=========================
def loading_sample_history() -> []:
    query_sample = '''
SELECT * FROM all_logs
WHERE all_logs.user_id = ?
'''
    bind_value = 0
    aligned_sample_histories = database_process(query_sample, bind_value)
    return aligned_sample_histories


def loading_all_history() -> []:
    query_sample = '''
SELECT * FROM all_logs
WHERE all_logs.user_id != ?
'''
    is_sample = idm_manager.current_is_sample()
    if is_sample:
        bind_value = 0
    else:
        bind_value = user_id_manager.user_id - 1

    aligned_all_histories = database_process(query_sample, bind_value)
    return aligned_all_histories


def loading_part_history() -> []:
    query_sample = '''
SELECT * FROM all_logs
WHERE all_logs.user_id = ?
'''
    bind_value = user_id_manager.user_id - 1
    aligned_all_histories = database_process(query_sample, bind_value)
    return aligned_all_histories


# ========================DB=========================
def database_process(query, bind_value) -> []:
    process_connection = sqlite3.connect(DATABASE_NAME)
    process_connection.row_factory = sqlite3.Row
    cursor = process_connection.cursor()
    cursor.execute(query, [bind_value])
    processed_histories = []
    for history in cursor.fetchall():
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
WHERE (stations.pref_cd = ? OR stations.pref_cd = ? OR stations.pref_cd = ? OR stations.pref_cd = ?) AND
cyberne_codes.line_key = ? AND
cyberne_codes.station_key = ?
LIMIT 1;
'''
    saitama_pref = 11
    chiba_pref = 12
    tokyo_pref = 13
    kanagawa_pref = 14
    cursor.execute(query, [saitama_pref, chiba_pref, tokyo_pref, kanagawa_pref, line_code, station_code])
    station = cursor.fetchone()
    if station is None:
        return None, None, None
    station_name = station['station_name']
    station_lon = station['lon']
    station_lat = station['lat']
    return station_name, station_lon, station_lat


def send_random_histories():
    for i in range(30):
        exists_none = True
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
        # if start_station is None or end_station is None:
        #     return
        start_station_name, start_station_lon, start_station_lat = start_station
        end_station_name, end_station_lon, end_station_lat = end_station
        if start_station_name is None or end_station_name is None:
            exists_none = False
        if exists_none:
            # print('start: ', start_station_name, start_station_lon, start_station_lat)
            # print('end: ', end_station_name, end_station_lon, end_station_lat)
            connection.close()
            client_manager.client_point.send_message('/line_random',
                                                     [start_station_name, start_station_lon, start_station_lat,
                                                      end_station_name, end_station_lon, end_station_lat])
            client_manager.client_between.send_message('/line_random',
                                                       [start_station_name, start_station_lon, start_station_lat,
                                                        end_station_name, end_station_lon, end_station_lat])
            client_manager.client_particle.send_message('/line_random',
                                                        [start_station_name, start_station_lon, start_station_lat,
                                                         end_station_name, end_station_lon, end_station_lat])
    print('random送ったよ')


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
    client_manager = ClientManager()
    clf = nfc.ContactlessFrontend('usb')
    clf.connect(rdwr={'on-connect': main, 'on-release': released})
