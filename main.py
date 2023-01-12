from time import sleep
from pythonosc import udp_client
import sqlite3

import nfc_sample
import test_cyberne_code_data
import nfc_reading
import csv
import struct
import nfc

ADDRESS = '127.0.0.1'
PORT = 12000
DATABASE_NAME = './History.db'
global user_id
global old_idm
global now_idm
global run_once_state
run_once_state = False
user_id = 0
now_idm = None
old_idm = None
count = None


# old_idm= 1


def main():
    global now_idm
    global old_idm
    client = udp_client.SimpleUDPClient(ADDRESS, PORT, True)
    sleep(1)
    # TODO: NFC読み込み
    clf = nfc.ContactlessFrontend('usb')
    clf.connect(rdwr={'on-connect': nfc_sample.connected})
    now_idm = nfc_reading.sender_idm()
    print(now_idm, ";" + old_idm)

    # TODO: NFC読み込み履歴をDBに保存
    preserve_history(now_idm, old_idm)

    # TODO: DBから履歴を読み込み

    # *** DBから緯度経度を検索 ***
    # テストデータからランダムに取得
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
    # *** 緯度と経度を送信 ***
    client.send_message('/line',
                        [start_station_name, start_station_lon, start_station_lat, end_station_name, end_station_lon,
                         end_station_lat])
    client.send_message('/action', [])


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
    # executeで実行
    # sql文で取り出す
    cursor.execute(query, [line_key, station_key])
    station = cursor.fetchone()
    if station is None:
        return
    station_name = station['station_name']
    station_lon = station['lon']
    station_lat = station['lat']
    return station_name, station_lon, station_lat


def preserve_history(now, old):
    if now is not old:
        global old_idm
        global now_idm
        global user_id
        old_idm = now_idm
        process, year, month, day, \
        start_station_name, start_station_line_code, start_station_code, \
        end_station_name, end_station_line_code, end_station_code \
            = nfc_reading.connected()
        if process is "運賃支払":
            preserve_to_db(start_station_name, start_station_line_code, start_station_code,
                             end_station_name, end_station_line_code, end_station_code,
                             user_id)
        user_id += 1
    else:
        return


# 履歴をDBへ保存
def preserve_to_db(start_station_name, start_station_line_code, start_station_code,
                   end_station_name, end_station_line_code, end_station_code,
                   user_id):
    preserve_connection = sqlite3.connect(DATABASE_NAME)
    cursor = preserve_connection.cursor()
    query = '''
INSERT INTO all_logs values (?,?,?,?,?,?,?)
'''
    cursor.execute(query, [start_station_name,
                           start_station_line_code,
                           start_station_code,
                           end_station_name,
                           end_station_line_code,
                           end_station_code,
                           user_id
                           ])
    preserve_connection.commit()
    preserve_connection.close()


# idmを保存
def copy_idm(new_idm):
    return new_idm


# 一度だけ実行
def run_once(idm):
    global run_once_state
    if not run_once_state:
        run_once_state = True
        return idm


# user_idの要素数をカウント
def count_all_logs():
    global user_id
    preserve_connection = sqlite3.connect(DATABASE_NAME)
    cursor = preserve_connection.cursor()
    query = '''
SELECT COUNT(all_logs.user_id = ? OR NULL) FROM all_logs
'''
    cursor.execute(query, [user_id - 1])
    user_id_count = cursor.fetchone()
    if user_id_count is None:
        return
    return user_id_count


if __name__ == '__main__':
    main()
