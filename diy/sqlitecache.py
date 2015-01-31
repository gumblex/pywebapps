import os
import sqlite3
import time
import hashlib
import collections
from itertools import islice

hashmd5 = lambda x: hashlib.md5(x.encode('utf-8')).digest()

class LRUCache:
    def __init__(self, maxlen):
        self.capacity = maxlen
        self.cache = collections.OrderedDict()

    def get(self, key):
        try:
            value = self.cache.pop(key)
            self.cache[key] = value
            return value
        except KeyError:
            return None

    def set(self, key, value):
        try:
            self.cache.pop(key)
        except KeyError:
            if len(self.cache) >= self.capacity:
                self.cache.popitem(last=False)
        self.cache[key] = value

    add = set

class SqliteCache:

    _create_sql = (
            'CREATE TABLE IF NOT EXISTS cache '
            '('
            '  key BLOB PRIMARY KEY,'
            '  val TEXT,'
            '  freq INTEGER'
            ')'
            )
    _len_sql = 'SELECT COUNT(*) FROM cache'
    _get_sql = 'SELECT val, freq FROM cache WHERE key = ?'
    _del_sql = 'DELETE FROM cache WHERE key = ?'
    _gc_sql = 'DELETE FROM cache WHERE key IN (SELECT key FROM cache WHERE freq = ? ORDER BY RANDOM() LIMIT ?)'
    _set_sql = 'REPLACE INTO cache (key, val, freq) VALUES (?, ?, ?)'
    _add_sql = 'INSERT INTO cache (key, val, freq) VALUES (?, ?, ?)'

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
        origdblen = dblen = conn.fetchone()[0]
        leastfreq = 1
        while dblen > self.maxlen:
            conn.execute(self._gc_sql, (leastfreq, dblen - self.maxlen))
            leastfreq += 1
            conn.execute(self._len_sql)
            dblen = conn.fetchone()[0]
        if origdblen%2:
            conn.execute('VACUUM')
        self.connection.commit()

    def clear(self):
        self.connection.commit()
        self.connection.close()
        self.__init__(self.path, self.maxlen)


class SqliteUserLog:

    _create_sql = (
            'CREATE TABLE IF NOT EXISTS userlog '
            '('
            '  rec INTEGER PRIMARY KEY ASC,'
            '  ip TEXT,'
            '  cnt INTEGER,'
            '  time INTEGER'
            ')'
            )
    _len_sql = 'SELECT COUNT(*) FROM userlog'
    _check_sql = 'SELECT SUM(cnt) FROM userlog WHERE (ip = ? AND time > ?)'
    _delete_sql = 'DELETE FROM userlog WHERE rec IN (SELECT rec FROM userlog WHERE ip = ?)'
    _gc_sql = 'DELETE FROM userlog WHERE rec IN (SELECT rec FROM userlog WHERE time < ?)'
    _add_sql = 'INSERT INTO userlog (ip, cnt, time) VALUES (?, ?, ?)'

    def __init__(self, path, maxcnt, expire=3600):
        self.path = os.path.abspath(path)
        self.maxcnt = maxcnt
        self.expire = expire
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

    def check(self, ip):
        conn = self.connection.cursor()
        conn.execute(self._check_sql, (ip, int(time.time() - self.expire)))
        reqcount = conn.fetchone()[0]
        return ((reqcount or 0) <= self.maxcnt)

    def count(self, ip):
        conn = self.connection.cursor()
        conn.execute(self._check_sql, (ip, int(time.time() - self.expire)))
        reqcount = conn.fetchone()[0]
        return reqcount or 0

    def add(self, ip, count):
        conn = self.connection.cursor()
        conn.execute(self._add_sql, (ip, count, int(time.time())))

    def delete(self, ip):
        conn = self.connection.cursor()
        conn.execute(self._delete_sql, (ip,))

    def gc(self):
        conn = self.connection.cursor()
        conn.execute(self._len_sql)
        origdblen = conn.fetchone()[0]
        conn.execute(self._gc_sql, (time.time() - self.expire,))
        if origdblen%2:
            conn.execute('VACUUM')
        self.connection.commit()

    def clear(self):
        self.connection.commit()
        self.connection.close()
        self.__init__(self.path, self.maxcnt, self.expire)

