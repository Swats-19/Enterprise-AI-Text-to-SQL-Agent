# this is like manager to the ecommerce file 

import sqlite3

db_name="ecommerce.db"

def get_connection():
    """creates n returns connection to the sqlite db"""

    conn=sqlite3.connect(db_name)

    return conn

def execute_query(query):
    """ Executes a select query and returns the results"""

    conn = get_connection()

    cursor = conn.cursor()

    cursor.execute(query)

    rows = cursor.fetchall()

    conn.close()

    return rows
