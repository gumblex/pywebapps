#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os
import sys
import sqlite3
from zlib import crc32 as _crc32
from sqlitecache import SqliteCache
from zhutil import calctxtstat
from config import *

crc32 = lambda s: _crc32(s.encode('utf-8')) & 0xffffffff

cache = SqliteCache(DB_zhccache, DB_zhccache_maxlen)

if os.path.isfile(DB_testsent):
	os.unlink(DB_testsent)
	#db = sqlite3.connect(DB_testsent)
	#cur = db.cursor()
#else:
db = sqlite3.connect(DB_testsent)
cur = db.cursor()
cur.execute("CREATE TABLE sentences (id INTEGER PRIMARY KEY, sent TEXT, type INTEGER)")
db.commit()

cf = open(os.path.join(OS_DATA, "zhc.txt")).read().split('\n')
mf = open(os.path.join(OS_DATA, "zhm.txt")).read().split('\n')

count = 0
ccount = 0
mcount = 0

for c,m in zip(cf, mf):
	if len(c) < 50:
		cache.set(c, m)
	if 15 < len(c) < 25:
		txt = c.strip('“”‘’；：')
		cscore, mscore = calctxtstat(txt)
		if abs(cscore - mscore) < 20:
			cur.execute("REPLACE INTO sentences (id, sent, type) VALUES (?, ?, ?)", (crc32(txt), txt, 0))
			ccount += 1
	if 15 < len(m) < 25:
		txt = m.strip('“”‘’；：')
		cscore, mscore = calctxtstat(txt)
		if abs(cscore - mscore) < 20:
			cur.execute("REPLACE INTO sentences (id, sent, type) VALUES (?, ?, ?)", (crc32(txt), txt, 1))
			mcount += 1
	count += 1
	if count % 100000 == 0:
		print(count)

print(count, ccount, mcount)
ccount = cur.execute("SELECT count(id) FROM sentences WHERE type = 0").fetchone()[0]
mcount = cur.execute("SELECT count(id) FROM sentences WHERE type = 1").fetchone()[0]
print(count, ccount, mcount)
cache.gc()
print('GC done.')

if ccount > mcount:
	cur.execute("DELETE FROM sentences WHERE id IN (SELECT id FROM sentences WHERE type = 0 ORDER BY RANDOM() LIMIT ?)", (ccount - mcount,))
else:
	cur.execute("DELETE FROM sentences WHERE id IN (SELECT id FROM sentences WHERE type = 1 ORDER BY RANDOM() LIMIT ?)", (mcount - ccount,))

db.commit()
print('TestSent done.')
