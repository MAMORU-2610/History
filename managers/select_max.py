import sqlite3
from config import DATABASE_NAME


def select_max():
    query = '''
SELECT MAX(user_id) as max_user_id FROM all_logs
'''
    connection = sqlite3.connect(DATABASE_NAME)
    connection.row_factory = sqlite3.Row
    cursor = connection.cursor()
    cursor.execute(query)
    result = cursor.fetchone()
    connection.close()
    return result['max_user_id']