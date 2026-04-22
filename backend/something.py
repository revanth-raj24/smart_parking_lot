import sqlite3
import mysql.connector

mysql_conn = mysql.connector.connect(
    host="localhost",
    user="smart_user",
    password="1234",
    database="smart_parking"
)

sqlite_conn = sqlite3.connect("new.db")

mysql_cursor = mysql_conn.cursor()
sqlite_cursor = sqlite_conn.cursor()

mysql_cursor.execute("SHOW TABLES")

for (table,) in mysql_cursor.fetchall():
    mysql_cursor.execute(f"SELECT * FROM {table}")
    rows = mysql_cursor.fetchall()

    # Create table manually before this step

    placeholders = ",".join(["?"] * len(rows[0]))
    sqlite_cursor.executemany(
        f"INSERT INTO {table} VALUES ({placeholders})", rows
    )

sqlite_conn.commit()