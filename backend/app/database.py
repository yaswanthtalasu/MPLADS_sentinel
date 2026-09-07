import os
import sqlite3
import pandas as pd
from typing import List, Dict, Any

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(os.path.dirname(os.path.dirname(BASE_DIR)), "mplads_prototype.db")

def get_db_connection():
    conn = sqlite3.connect(DB_PATH, timeout=10.0, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def execute_query(query: str, params: tuple = ()) -> List[Dict[str, Any]]:
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(query, params)
        rows = cursor.fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()

def execute_update(query: str, params: tuple = ()):
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(query, params)
        conn.commit()
    finally:
        conn.close()
