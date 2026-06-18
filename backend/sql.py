# pyrefly: ignore [missing-import]
import mysql.connector

conn = mysql.connector.connect(
    host="localhost",
    user="root",
    password="GhUF@702",
    database="omniroute"
)

print("Connected Successfully!")