#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os
import sys
import sqlite3
from sqlitecache import SqliteCache
from config import *

cache = SqliteCache(DB_zhccache, DB_zhccache_maxlen)

if os.path.isfile(DB_testsent):
	db = sqlite3.connect(DB_testsent)
	cur = db.cursor()
else:
	db = sqlite3.connect(DB_testsent)
	cur = db.cursor()
	cur.execute("CREATE TABLE sentences (sent TEXT PRIMARY KEY, type INTEGER)")
	db.commit()

cf = open(os.path.join(OS_DATA, "zhc.txt")).read().split('\n')
mf = open(os.path.join(OS_DATA, "zhm.txt")).read().split('\n')

count = 0

for c,m in zip(cf, mf):
	cache.set(c, m)
	if 15 < len(c) < 25:
		cur.execute("REPLACE INTO sentences (sent, type) VALUES (?, ?)", (c.strip('“”‘’'), 0))
	if 15 < len(m) < 25:
		cur.execute("REPLACE INTO sentences (sent, type) VALUES (?, ?)", (m.strip('“”‘’'), 1))
	count += 1
	if count % 10000 == 0:
		print(count)

cache.gc()
db.commit()
db.close()
