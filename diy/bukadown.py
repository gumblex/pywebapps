#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import time
import gzip
import json
import functools
import urllib.request, urllib.parse
from sqlitecache import SqliteIntCache
from config import *

def bukadownloader(comicid, chapid):
	"""
	Experimental Buka downloader.
	Supports buka file only.

	Current findings are listed as follow:

	There is a JSON (RPC-like) interface at
	http://cs.bukamanhua.com:8000/request.php?t=%d
	where we can POST a JSON function.
	So far we have found these:
	('func_getsimpleinfo', 'func_getdetail', 'func_getdownurl3', 'func_getglobalvar', 'func_recomhome3')
	The response is a JSON object with 'ret' value guaranteed. 0 for success.

	To download corresponding index2.dat, GET
	'http://index.bukamanhua.com:8000/req3.php?mid=%s&cid=%s&c=f76b8c7a03490e06bb3389544bc527a5&s=ad&v=5&t=-1&restype=2&cv=17301551' % (comicid, chapid)

	In index2.dat there is a gzipped (b'\x1f\x8b') JSON object, like this:
	{"resbk":"http:\\/\\/c-pic3.weikan.cn\\/pich","resbklist":["http:\\/\\/c-r2.sosobook.cn\\/pich","http:\\/\\/c-pic3.weikan.cn\\/pich"],"idxver":"137960966","restype":2}
	"""
	postdata = ('i=%s&z=1&p=android&v=9&c=91643f635a86aad35b9f942db576f233' % urllib.parse.quote(urllib.parse.quote(json.dumps({"f":"func_getdownurl3","ver":3,"mid":comicid,"cid":chapid,"restype":2})))).encode('utf-8')
	req = urllib.request.Request("http://cs.bukamanhua.com:8000/request.php?t=%d" % time.time(), data=postdata, headers={"Content-Type": "application/x-www-form-urlencoded"})
	downlist = json.loads(gzip.decompress(urllib.request.urlopen(req).read()).decode('utf-8'))
	if downlist['ret']:
		return None
	downlist = downlist["down"]
	defaultheader = {
		'Accept-Encoding': 'gzip,deflate',
		'User-Agent': 'Mozilla/5.0 (Windows NT 5.1) AppleWebKit/535.12 (KHTML, like Gecko) Maxthon/3.3.4.4000 Chrome/18.0.966.0 Safari/535.12',
		'Connection': 'Keep-Alive',
	}
	for obj in downlist:
		if int(obj["urltype"]) == 2:
			return obj["url"]
	return None


@functools.lru_cache(maxsize=1024)
def getbukaurl(comicid, chapid):
	sqlcache = SqliteIntCache(DB_bukacache, 65536)
	rv = sqlcache.get(comicid*1000000 + chapid)
	if rv:
		return rv
	rv = bukadownloader(comicid, chapid)
	sqlcache.add(comicid*1000000 + chapid, rv)
	return rv
