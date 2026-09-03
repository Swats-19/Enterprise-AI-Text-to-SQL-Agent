import sqlite3

from db import get_connection


def execute_sql(sql_query: str):

    connection = get_connection()

    cursor = connection.cursor()

    try:

        cursor.execute(sql_query)

        rows = cursor.fetchall()

        column_names = [description[0] for description in cursor.description]

        return column_names, rows

    finally:

        connection.close()