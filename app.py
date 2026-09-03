import sqlite3

connection = sqlite3.connect("ecommerce.db")

cursor = connection.cursor()

with open("schema.sql", "r") as f:
    cursor.executescript(f.read())

connection.commit()

print("Database Created Successfully!")

connection.close()