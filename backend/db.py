# Database management helper functions for MySQL

import os
import re
from urllib.parse import urlparse
from flask import has_app_context, g
from dotenv import load_dotenv
import mysql.connector
from mysql.connector.pooling import MySQLConnectionPool

# Helper flags
dotenv_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env')
load_dotenv(dotenv_path)

DATABASE_URL = os.environ.get('DATABASE_URL', '')
IS_POSTGRES = False
IS_MYSQL = True

# Conditional imports
mysql_pool = None

try:
    parsed = urlparse(DATABASE_URL)
    pool_config = {
        'host': parsed.hostname,
        'user': parsed.username,
        'password': parsed.password,
        'port': parsed.port or 3306,
        'database': parsed.path.lstrip('/'),
        'pool_name': 'sharadha_mysql_pool',
        'pool_size': 5
    }
    mysql_pool = MySQLConnectionPool(**pool_config)
except Exception as e:
    print(f"Error initializing MySQL Connection Pool: {e}")

class MySQLCursorWrapper:
    def __init__(self, cursor):
        self._cursor = cursor
    def __getattr__(self, name):
        return getattr(self._cursor, name)
    def execute(self, query, args=None):
        if query:
            query = query.replace('?', '%s')
            if "BEGIN TRANSACTION" in query.upper():
                query = re.sub(r'BEGIN\s+TRANSACTION', 'START TRANSACTION', query, flags=re.IGNORECASE)
        return self._cursor.execute(query, args)
    def executemany(self, query, args_list):
        if query:
            query = query.replace('?', '%s')
            if "BEGIN TRANSACTION" in query.upper():
                query = re.sub(r'BEGIN\s+TRANSACTION', 'START TRANSACTION', query, flags=re.IGNORECASE)
        return self._cursor.executemany(query, args_list)

class MySQLConnectionWrapper:
    def __init__(self, conn):
        self._conn = conn
    def __getattr__(self, name):
        return getattr(self._conn, name)
    def close(self, force=False):
        if force or not has_app_context():
            self._conn.close()
    def cursor(self, *args, **kwargs):
        kwargs.setdefault('dictionary', True)
        kwargs.setdefault('buffered', True)
        raw_cursor = self._conn.cursor(*args, **kwargs)
        return MySQLCursorWrapper(raw_cursor)
    def execute(self, query, args=()):
        cur = self.cursor()
        cur.execute(query, args)
        return cur
    def executescript(self, script):
        cur = self._conn.cursor()
        for statement in script.split(';'):
            stmt_clean = statement.strip()
            if stmt_clean:
                stmt_clean = stmt_clean.replace('?', '%s')
                cur.execute(stmt_clean)
        cur.close()

def connect_mysql():
    global mysql_pool
    if mysql_pool is not None:
        try:
            return mysql_pool.get_connection()
        except Exception as e:
            print(f"Failed to get pooled connection: {e}")
            
    parsed = urlparse(DATABASE_URL)
    config = {
        'host': parsed.hostname,
        'user': parsed.username,
        'password': parsed.password,
        'port': parsed.port or 3306,
        'database': parsed.path.lstrip('/')
    }
    conn = mysql.connector.connect(**config)
    return conn

def get_db():
    """Returns a connection to the MySQL database."""
    if has_app_context():
        if 'db' not in g:
            g.db = MySQLConnectionWrapper(connect_mysql())
        return g.db
    else:
        return MySQLConnectionWrapper(connect_mysql())

def init_db():
    """Executes the schema.sql script to build the tables in MySQL."""
    schema_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'schema.sql')
    if not os.path.exists(schema_path):
        raise FileNotFoundError(f"Schema file not found at {schema_path}")
        
    conn = get_db()
    try:
        with open(schema_path, 'r', encoding='utf-8') as f:
            schema_sql = f.read()
            
        schema_sql = re.sub(r'INTEGER\s+PRIMARY\s+KEY\s+AUTOINCREMENT', 'INTEGER PRIMARY KEY AUTO_INCREMENT', schema_sql, flags=re.IGNORECASE)
        schema_sql = re.sub(r'TEXT\s+NOT\s+NULL\s+UNIQUE', 'VARCHAR(255) NOT NULL UNIQUE', schema_sql, flags=re.IGNORECASE)
        schema_sql = re.sub(r'TEXT\s+DEFAULT\s+CURRENT_TIMESTAMP', 'DATETIME DEFAULT CURRENT_TIMESTAMP', schema_sql, flags=re.IGNORECASE)
        schema_sql = re.sub(r'TEXT(\s+NOT\s+NULL)?\s+DEFAULT', r'VARCHAR(255)\1 DEFAULT', schema_sql, flags=re.IGNORECASE)
        conn.executescript(schema_sql)
            
        # Ensure password column exists in customers table
        try:
            cur = conn.execute("SELECT password FROM customers LIMIT 1")
            cur.fetchall()
            cur.close()
        except Exception:
            conn.rollback()
            cur = conn.execute("ALTER TABLE customers ADD COLUMN password VARCHAR(255) NOT NULL DEFAULT 'customerpassword'")
            cur.close()
            conn.commit()
            
        # Create admin_credentials table if not exists and seed default admin
        cur = conn.execute("""
            CREATE TABLE IF NOT EXISTS admin_credentials (
                username VARCHAR(255) PRIMARY KEY,
                password TEXT NOT NULL
            );
        """)
        cur.close()
        cur = conn.execute("""
            INSERT IGNORE INTO admin_credentials (username, password)
            VALUES ('admin@sharadhastores.com', 'adminpassword');
        """)
        cur.close()
        conn.commit()
    finally:
        conn.close()
    print("Database initialized successfully.")

def query_db(query, args=(), one=False):
    """Utility function to query the database and return results as dictionaries."""
    conn = get_db()
    try:
        cur = conn.cursor()
        translated = query.replace('?', '%s')
        cur.execute(translated, args)
        results = cur.fetchall()
        cur.close()
        return (results[0] if results else None) if one else results
    finally:
        conn.close()

def insert_db(query, args=()):
    """Utility function to insert data and return the last row ID."""
    conn = get_db()
    try:
        cur = conn.cursor()
        translated = query.replace('?', '%s')
        cur.execute(translated, args)
        last_id = cur.lastrowid
        conn.commit()
        cur.close()
        return last_id
    finally:
        conn.close()

def execute_db(query, args=()):
    """Utility function to execute a write/update command."""
    conn = get_db()
    try:
        cur = conn.cursor()
        translated = query.replace('?', '%s')
        cur.execute(translated, args)
        conn.commit()
        cur.close()
    finally:
        conn.close()
