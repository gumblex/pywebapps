import os, sqlite3
from itertools import islice
import hashlib

hashmd5 = lambda x: hashlib.md5(x.encode('utf-8')).digest()

class SqliteCache:

    _create_sql = (
            'CREATE TABLE IF NOT EXISTS bucket '
            '('
            '  key BLOB PRIMARY KEY,'
            '  val TEXT,'
            '  freq INTEGER'
            ')'
            )
    _len_sql = 'SELECT COUNT(*) FROM bucket'
    _get_sql = 'SELECT val, freq FROM bucket WHERE key = ?'
    _getone_sql = 'SELECT key FROM bucket WHERE freq = 1'
    _del_sql = 'DELETE FROM bucket WHERE key = ?'
    _set_sql = 'REPLACE INTO bucket (key, val, freq) VALUES (?, ?, ?)'
    _add_sql = 'INSERT INTO bucket (key, val, freq) VALUES (?, ?, ?)'

    def __init__(self, path, maxlen=1048576):
        self.path = os.path.abspath(path)
        self.maxlen = maxlen
        if not os.path.isfile(self.path):
            self.connection = sqlite3.connect(self.path)
            self.connection.execute(self._create_sql)
        else:
            self.connection = sqlite3.connect(self.path)

    def __del__(self):
        self.connection.commit()
        self.connection.close()

    def commit(self):
        self.connection.commit()

    def get(self, key):
        rv = None
        conn = self.connection.cursor()
        key = hashmd5(key)
        conn.execute(self._get_sql, (key,))
        row = conn.fetchone()
        if row:
            rv = row[0]
            freq = row[1]
            conn.execute(self._set_sql, (key, rv, freq + 1))
        return rv

    def delete(self, key):
        conn = self.connection.cursor()
        key = hashmd5(key)
        conn.execute(self._del_sql, (key,))

    def set(self, key, value):
        conn = self.connection.cursor()
        key = hashmd5(key)
        conn.execute(self._set_sql, (key, value, 1))

    def add(self, key, value):
        conn = self.connection.cursor()
        key = hashmd5(key)
        try:
            conn.execute(self._add_sql, (key, value, 1))
        except sqlite3.IntegrityError:
            conn.execute(self._get_sql, (key,))
            row = conn.fetchone()
            value = row[0]
            freq = row[1]
            conn.execute(self._set_sql, (key, value, freq + 1))

    def gc(self):
        conn = self.connection.cursor()
        conn.execute(self._len_sql)
        dblen = conn.fetchone()[0]
        if dblen > self.maxlen:
            deletekeys = tuple(islice(conn.execute(self._getone_sql), dblen - self.maxlen))
            for row in deletekeys:
                conn.execute(self._del_sql, (row[0],))
        self.connection.commit()

    def clear(self):
        self.connection.commit()
        self.connection.close()
        self.__init__(self, self.path)
