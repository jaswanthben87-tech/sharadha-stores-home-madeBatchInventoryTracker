# Database management helper functions for SQLite, PostgreSQL, and MySQL

import sqlite3
import os
import re
from urllib.parse import urlparse, parse_qs
from flask import has_app_context, g

# Helper flags
DATABASE_URL = os.environ.get('DATABASE_URL', '')
IS_POSTGRES = 'postgres' in DATABASE_URL.lower()
IS_MYSQL = 'mysql' in DATABASE_URL.lower()

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'tracker.db')

# Conditional imports
if IS_POSTGRES:
    import psycopg2
    from psycopg2.extras import RealDictCursor
elif IS_MYSQL:
    import mysql.connector

class SQLiteConnectionWrapper:
    def __init__(self, conn):
        self._conn = conn
    def __getattr__(self, name):
        return getattr(self._conn, name)
    def close(self):
        # Manual close calls inside Flask context are no-ops because
        # teardown_appcontext closes the actual connection.
        if not has_app_context():
            self._conn.close()

class PostgresConnectionWrapper:
    def __init__(self, conn):
        self._conn = conn
    def __getattr__(self, name):
        return getattr(self._conn, name)
    def close(self):
        if not has_app_context():
            self._conn.close()
    def cursor(self, *args, **kwargs):
        from psycopg2.extras import RealDictCursor
        kwargs.setdefault('cursor_factory', RealDictCursor)
        return self._conn.cursor(*args, **kwargs)
    def execute(self, query, args=()):
        cur = self.cursor()
        translated_query = query.replace('?', '%s')
        cur.execute(translated_query, args)
        return cur
    def executescript(self, script):
        cur = self._conn.cursor()
        cur.execute(script)
        cur.close()

class MySQLConnectionWrapper:
    def __init__(self, conn):
        self._conn = conn
    def __getattr__(self, name):
        return getattr(self._conn, name)
    def close(self):
        if not has_app_context():
            self._conn.close()
    def cursor(self, *args, **kwargs):
        kwargs.setdefault('dictionary', True)
        return self._conn.cursor(*args, **kwargs)
    def execute(self, query, args=()):
        cur = self.cursor()
        translated_query = query.replace('?', '%s')
        cur.execute(translated_query, args)
        return cur
    def executescript(self, script):
        cur = self._conn.cursor()
        for statement in script.split(';'):
            stmt_clean = statement.strip()
            if stmt_clean:
                cur.execute(stmt_clean)
        cur.close()

def connect_postgres():
    url = DATABASE_URL
    if url.startswith('postgres://'):
        url = url.replace('postgres://', 'postgresql://', 1)
    return psycopg2.connect(url)

def connect_mysql():
    parsed = urlparse(DATABASE_URL)
    config = {
        'host': parsed.hostname,
        'user': parsed.username,
        'password': parsed.password,
        'port': parsed.port or 3306,
        'database': parsed.path.lstrip('/')
    }
    
    # Extract SSL parameters if present in the query string
    query = parse_qs(parsed.query)
    if 'ssl-mode' in query:
        config['ssl_mode'] = query['ssl-mode'][0]
    elif 'ssl_mode' in query:
        config['ssl_mode'] = query['ssl_mode'][0]
        
    conn = mysql.connector.connect(**config)
    return conn

def get_db():
    """Returns a connection to the SQLite, PostgreSQL, or MySQL database."""
    if has_app_context():
        if 'db' not in g:
            if IS_POSTGRES:
                g.db = PostgresConnectionWrapper(connect_postgres())
            elif IS_MYSQL:
                g.db = MySQLConnectionWrapper(connect_mysql())
            else:
                conn = sqlite3.connect(DB_PATH)
                conn.row_factory = sqlite3.Row
                conn.execute("PRAGMA foreign_keys = ON;")
                g.db = conn
        if IS_POSTGRES or IS_MYSQL:
            return g.db
        else:
            return SQLiteConnectionWrapper(g.db)
    else:
        if IS_POSTGRES:
            return PostgresConnectionWrapper(connect_postgres())
        elif IS_MYSQL:
            return MySQLConnectionWrapper(connect_mysql())
        else:
            conn = sqlite3.connect(DB_PATH)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA foreign_keys = ON;")
            return conn

def init_db():
    """Executes the schema.sql script to build the tables in SQLite/PostgreSQL/MySQL."""
    schema_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'schema.sql')
    if not os.path.exists(schema_path):
        raise FileNotFoundError(f"Schema file not found at {schema_path}")
        
    conn = get_db()
    try:
        with open(schema_path, 'r', encoding='utf-8') as f:
            schema_sql = f.read()
            
        if IS_POSTGRES:
            schema_sql = re.sub(r'INTEGER\s+PRIMARY\s+KEY\s+AUTOINCREMENT', 'SERIAL PRIMARY KEY', schema_sql, flags=re.IGNORECASE)
            conn.executescript(schema_sql)
        elif IS_MYSQL:
            schema_sql = re.sub(r'INTEGER\s+PRIMARY\s+KEY\s+AUTOINCREMENT', 'INTEGER PRIMARY KEY AUTO_INCREMENT', schema_sql, flags=re.IGNORECASE)
            conn.executescript(schema_sql)
        else:
            conn.executescript(schema_sql)
            
        # Ensure password column exists in customers table
        try:
            conn.execute("SELECT password FROM customers LIMIT 1")
        except Exception:
            if IS_POSTGRES or IS_MYSQL:
                conn.rollback()
            conn.execute("ALTER TABLE customers ADD COLUMN password TEXT NOT NULL DEFAULT 'customerpassword'")
            conn.commit()
            
        # Create admin_credentials table if not exists and seed default admin
        if IS_POSTGRES:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS admin_credentials (
                    username TEXT PRIMARY KEY,
                    password TEXT NOT NULL
                );
            """)
            conn.execute("""
                INSERT INTO admin_credentials (username, password)
                VALUES ('admin@sharadhastores.com', 'adminpassword')
                ON CONFLICT (username) DO NOTHING;
            """)
        elif IS_MYSQL:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS admin_credentials (
                    username VARCHAR(255) PRIMARY KEY,
                    password TEXT NOT NULL
                );
            """)
            conn.execute("""
                INSERT IGNORE INTO admin_credentials (username, password)
                VALUES ('admin@sharadhastores.com', 'adminpassword');
            """)
        else:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS admin_credentials (
                    username TEXT PRIMARY KEY,
                    password TEXT NOT NULL
                );
            """)
            conn.execute("""
                INSERT OR IGNORE INTO admin_credentials (username, password)
                VALUES ('admin@sharadhastores.com', 'adminpassword');
            """)
        conn.commit()
    finally:
        conn.close()
    print("Database initialized successfully.")

def query_db(query, args=(), one=False):
    """Utility function to query the database and return results as dictionaries."""
    conn = get_db()
    try:
        cur = conn.cursor()
        if IS_POSTGRES or IS_MYSQL:
            translated = query.replace('?', '%s')
            cur.execute(translated, args)
            results = cur.fetchall()
        else:
            cur.execute(query, args)
            rv = cur.fetchall()
            columns = [col[0] for col in cur.description] if cur.description else []
            results = [dict(zip(columns, row)) for row in rv]
        cur.close()
        return (results[0] if results else None) if one else results
    finally:
        conn.close()

def insert_db(query, args=()):
    """Utility function to insert data and return the last row ID."""
    conn = get_db()
    try:
        cur = conn.cursor()
        if IS_POSTGRES or IS_MYSQL:
            translated = query.replace('?', '%s')
            cur.execute(translated, args)
            if IS_POSTGRES:
                cur.execute("SELECT LASTVAL()")
                row = cur.fetchone()
                last_id = list(row.values())[0] if isinstance(row, dict) else row[0]
            else: # MySQL
                last_id = cur.lastrowid
        else:
            cur.execute(query, args)
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
        if IS_POSTGRES or IS_MYSQL:
            translated = query.replace('?', '%s')
            cur.execute(translated, args)
        else:
            cur.execute(query, args)
        conn.commit()
        cur.close()
    finally:
        conn.close()
