#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import struct
import socket
import threading
import socketserver

import re
import time
import signal
import resource
import subprocess
from functools import lru_cache
from operator import itemgetter

import jieba
import jiebazhc
import zhutil
import umsgpack
from zhconv import convert as zhconv
from sqlitecache import LRUCache, SqliteCache
from config import *

SIGNUM2NAME = dict((k, v) for v, k in signal.__dict__.items() if v.startswith(
	'SIG') and not v.startswith('SIG_'))

os.chdir(os.path.dirname(os.path.abspath(sys.argv[0])))

resource.setrlimit(
	resource.RLIMIT_RSS, (MOSES_MAXMEM * 1024 - 10000, MOSES_MAXMEM * 1024))

c2m = [MOSESBIN, '-v', '0', '-f', MOSES_INI_c2m]
m2c = [MOSESBIN, '-v', '0', '-f', MOSES_INI_m2c]

punct = frozenset(
	''':!),.:;?]}¢'"、。〉》」』】〕〗〞︰︱︳﹐､﹒﹔'''
	'''﹕﹖﹗﹚﹜﹞！），．：；？｜｝︴︶︸︺︼︾﹀﹂﹄﹏､'''
	'''～￠々‖•·ˇˉ―--′’”([{£¥'"‵〈《「『【〔〖（［｛'''
	'''￡￥〝︵︷︹︻︽︿﹁﹃﹙﹛﹝（｛“‘'''
)
longpunct = frozenset('-—_…')
whitespace = frozenset(' \t\n\r\x0b\x0c\u3000')

RE_WS_IN_FW = re.compile(
r'([\u2018\u2019\u201c\u201d\u2026\u2e80-\u312f\u3200-\u32ff\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff\ufe30-\ufe57\uff00-\uffef])\s+(?=[\u2018\u2019\u201c\u201d\u2026\u2e80-\u312f\u3200-\u32ff\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff\ufe30-\ufe57\uff00-\uffef])'
)

RE_UCJK = re.compile('([\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]+)')

detokenize = lambda s: RE_WS_IN_FW.sub(r'\1', xml_unescape(s)).strip()

runmoses = lambda mode: (
	subprocess.Popen(m2c, shell=False, stdin=subprocess.PIPE,
					 stdout=subprocess.PIPE, stderr=sys.stderr, cwd=MOSES_CWD)
	if mode == 'm2c'
	else
	subprocess.Popen(c2m, shell=False, stdin=subprocess.PIPE,
					 stdout=subprocess.PIPE, stderr=sys.stderr, cwd=MOSES_CWD)
)

xml_escape_table = {
	"&": "&amp;", '"': "&quot;", "'": "&apos;",
	">": "&gt;", "<": "&lt;",
}

xml_unescape_table = {
	"&amp;": "&", "&quot;": '"', "&apos;": "'",
	"&gt;": ">", "&lt;": "<",
}


mc = None

def xml_escape(text):
	"""Produce entities within text."""
	return "".join(xml_escape_table.get(c, c) for c in text)


def xml_unescape(text):
	"""Produce entities within text."""
	return " ".join(xml_unescape_table.get(c, c) for c in text.split(' '))


def recvall(sock, buf=1024):
	data = sock.recv(buf)
	alldata = [data]
	while data and data[-1] != 0xc1:
		data = sock.recv(buf)
		alldata.append(data)
	return b''.join(alldata)[:-1]


def sendall(sock, data):
	sock.sendall(data + b'\xc1')


class ThreadedUStreamRequestHandler(socketserver.BaseRequestHandler):

	def handle(self):
		msg = handlemsg(recvall(self.request))
		if msg == b'stop':
			self.server.shutdown()
		elif msg:
			sendall(self.request, msg)


class ThreadedUStreamServer(
		socketserver.ThreadingMixIn, socketserver.UnixStreamServer):
	pass


class MosesManagerThread:

	def __init__(self, mode, lock):
		self.mode = mode
		if self.mode == "c2m":
			self.sqlcache = SqliteCache(DB_zhccache, DB_zhccache_maxlen)
		else:
			self.sqlcache = None
		self.lrucache = LRUCache(128)
		self.proc = runmoses(mode)
		sys.stderr.write('Started Moses %s: %s\n' % (mode, self.proc.pid))
		sys.stderr.write('System ready.\n')
		sys.stderr.flush()
		self.lock = lock
		self.run = True
		self.taskqueue = []
		self.resultqueue = []
		self._ig = itemgetter(1)

	def checkmoses(self):
		returncode = self.proc.poll()
		if returncode is not None:
			sys.stderr.write('Moses %s (%s) is dead: %s\n' % (
				self.mode,
				self.proc.pid,
				SIGNUM2NAME.get(-returncode, str(returncode))))
			self.proc.wait()
			self.proc = runmoses(self.mode)
			sys.stderr.write('Restarted Moses %s: %s\n' % (
				self.mode, self.proc.pid))
		return self.proc

	def tokenize(self, s):
		if self.mode == "c2m":
			cut = jiebazhc.cut
		else:
			cut = jieba.cut
		tokens = []
		for t in RE_UCJK.split(s):
			tok = t.strip()
			if tok:
				if RE_UCJK.match(tok):
					tokens.extend(cut(tok))
				else:
					tokens.extend(xml_escape(tok).split())
		return ' '.join(zhutil.addwalls(tokens))

	def processtasks(self):
		if not self.taskqueue:
			return True
		elif not self.run:
			return False
		proc = self.checkmoses()
		for sn, s in self.taskqueue:
			tok = self.tokenize(s)
			proc.stdin.write(('%s\n' % tok).encode('utf8'))
		proc.stdin.flush()
		for sn, s in self.taskqueue:
			rv = detokenize(proc.stdout.readline().decode('utf8'))
			if not rv:
				return False
			self.resultqueue.append((sn, rv))
			self.lrucache.add(s, rv)
			if self.mode == "c2m":
				self.sqlcache.add(s, rv)
		return True

	def getcache(self, text):
		if not any(0x4DFF < ord(ch) < 0x9FCD for ch in text):
			# no chinese
			return text
		# put conversion here
		text = zhutil.hw2fw(text)
		rv = self.lrucache.get(text)
		if rv is None and self.mode == "c2m":
			rv = self.sqlcache.get(text)
		return rv

	def translate(self, text, withcount=False):
		hitcount = 0
		misscount = 0
		snum = 0
		with self.lock:
			if not self.run:
				return
			self.taskqueue = []
			self.resultqueue = []
			timestart = time.time()
			for l in text.split('\n'):
				sentences = zhutil.splithard(zhconv(l.strip(), 'zh-cn'), 128)
				for s in sentences:
					if s:
						crv = self.getcache(s)
						if crv:
							self.resultqueue.append((snum, crv))
							hitcount += 1
						else:
							self.taskqueue.append((snum, s))
							misscount += 1
					else:
						self.resultqueue.append((snum, s))
					snum += 1
				self.resultqueue.append((snum, '\n'))
				snum += 1
			try:
				res = self.processtasks()  # Error handling?
			except Exception:
				res = False
			self.resultqueue.sort()
			sys.stderr.write('%s,%s,%s,%s,%s,%.6f\n' % (
				time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime()), self.mode,
				misscount, hitcount + misscount, len(text),
				time.time() - timestart))
			outputtext = ''.join(map(self._ig, self.resultqueue))
		if withcount:
			return (outputtext, misscount)
		else:
			return outputtext

	def shutdown(self):
		self.run = False
		self.proc.terminate()
		if self.sqlcache:
			self.sqlcache.gc()

class MosesContext:

	def __init__(self):
		self.c2mlock = threading.Lock()
		self.m2clock = threading.Lock()
		self.c2m = MosesManagerThread('c2m', self.c2mlock)
		self.m2c = MosesManagerThread('m2c', self.m2clock)

	def shutdown(self):
		self.c2m.shutdown()
		self.m2c.shutdown()


def handlemsg(data):
	oper = umsgpack.loads(data)
	if oper[0] == 'c2m':
		return umsgpack.dumps(mc.c2m.translate(oper[1], oper[2]))
	elif oper[0] == 'm2c':
		return umsgpack.dumps(mc.m2c.translate(oper[1], oper[2]))
	elif oper[0] == 'cut':
		return umsgpack.dumps(tuple(jieba.cut(*oper[1], **oper[2])))
	elif oper[0] == 'cut_for_search':
		return umsgpack.dumps(tuple(jieba.cut_for_search(*oper[1], **oper[2])))
	elif oper[0] == 'tokenize':
		return umsgpack.dumps(tuple(jieba.tokenize(*oper[1], **oper[2])))
	elif oper[0] == 'jiebazhc.cut':
		return umsgpack.dumps(tuple(jiebazhc.cut(*oper[1], **oper[2])))
	elif oper[0] == 'jiebazhc.cut_for_search':
		return umsgpack.dumps(
			tuple(jiebazhc.cut_for_search(*oper[1], **oper[2])))
	elif oper[0] == 'jiebazhc.tokenize':
		return umsgpack.dumps(tuple(jiebazhc.tokenize(*oper[1], **oper[2])))
	elif oper[0] == 'add_word':
		jieba.add_word(*oper[1], **oper[2])
	elif oper[0] == 'load_userdict':
		jieba.load_userdict(*oper[1])
	elif oper[0] == 'set_dictionary':
		jieba.set_dictionary(*oper[1])
	elif oper[0] == 'stopserver':
		return b'stop'
	elif oper[0] == 'ping':
		return b'pong'


def serve(filename):
	global mc
	if os.path.exists(filename):
		try:
			receive(filename, umsgpack.dumps(('ping',)))
			print("Server already started.")
			return False
		except Exception:
			# not removed socket
			print("Found abandoned socket")
			os.unlink(filename)
	try:
		mc = MosesContext()
		server = ThreadedUStreamServer(filename, ThreadedUStreamRequestHandler)
		server.serve_forever()
	finally:
		server.shutdown()
		mc.shutdown()
		if os.path.exists(filename):
			os.unlink(filename)
		sys.stderr.flush()
		print("Server stopped.")


if __name__ == "__main__":
	filename = MS_SOCK
	try:
		serve(filename)
	except OSError as ex:
		if 'Address already in use' in str(ex):
			print("Server already started.")
