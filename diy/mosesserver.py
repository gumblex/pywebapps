#!/usr/bin/env python3
import sys, os
import re
import umsgpack
import subprocess
import socket
import signal
import time
from functools import lru_cache
from operator import itemgetter
import resource

from zhconv import convert as zhconv
import zhutil
import jieba
import jiebazhc
from sqlitecache import LRUCache, SqliteCache
from config import *

#_curpath = os.path.normpath(os.path.join(os.getcwd(), os.path.dirname(__file__)))
#TIMEOUT_path = os.path.join(_curpath, 'timeout')

os.chdir(os.path.dirname(os.path.abspath(sys.argv[0])))

SIGNUM2NAME = dict((k, v) for v, k in signal.__dict__.items() if v.startswith('SIG') and not v.startswith('SIG_'))

resource.setrlimit(resource.RLIMIT_RSS, (MOSES_MAXMEM*1024 - 10000, MOSES_MAXMEM*1024))

c2m = [MOSESBIN, '-v', '0', '-f', MOSES_INI_c2m]
m2c = [MOSESBIN, '-v', '0', '-f', MOSES_INI_m2c]
#c2m = [TIMEOUT_path, '-m', MOSES_MAXMEM, MOSESBIN, '-v', '0', '-f', MOSES_INI_c2m]
#m2c = [TIMEOUT_path, '-m', MOSES_MAXMEM, MOSESBIN, '-v', '0', '-f', MOSES_INI_m2c]
punct = frozenset(''':!),.:;?]}¢'"、。〉》」』】〕〗〞︰︱︳﹐､﹒﹔﹕﹖﹗﹚﹜﹞！），．：；？｜｝︴︶︸︺︼︾﹀﹂﹄﹏､～￠々‖•·ˇˉ―--′’”([{£¥'"‵〈《「『【〔〖（［｛￡￥〝︵︷︹︻︽︿﹁﹃﹙﹛﹝（｛“‘''')
longpunct = frozenset('-—_…')
whitespace = frozenset(' \t\n\r\x0b\x0c\u3000')
notwhite = lambda x: x not in whitespace

RE_WS_IN_FW = re.compile(r'([\u2018\u2019\u201c\u201d\u2e80-\u312f\u3200-\u32ff\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff\uff00-\uffef])\s+(?=[\u2018\u2019\u201c\u201d\u2e80-\u312f\u3200-\u32ff\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff\uff00-\uffef])')

detokenize = lambda s: RE_WS_IN_FW.sub(r'\1', xml_unescape(s)).strip()

quiet = False
verbose = False

runmoses = lambda mode: subprocess.Popen(m2c, shell=False, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=sys.stderr, cwd=MOSES_CWD) if mode=='m2c' else subprocess.Popen(c2m, shell=False, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=sys.stderr, cwd=MOSES_CWD)

xml_escape_table = {
	"&": "&amp;", '"': "&quot;", "'": "&apos;",
	">": "&gt;", "<": "&lt;",
}

xml_unescape_table = {
	"&amp;": "&", "&quot;": '"', "&apos;": "'",
	"&gt;": ">", "&lt;": "<",
}

def xml_escape(text):
    """Produce entities within text."""
    return "".join(xml_escape_table.get(c,c) for c in text)

def xml_unescape(text):
    """Produce entities within text."""
    return " ".join(xml_unescape_table.get(c,c) for c in text.split(' '))

class MosesManagerThread:
	def __init__(self):
		self.sqlcache = SqliteCache(DB_zhccache, DB_zhccache_maxlen)
		self.lrucache = LRUCache(128)
		self.pc2m = runmoses('c2m')
		self.pm2c = runmoses('m2c')
		sys.stderr.write('Started Moses c2m: %s\n' % self.pc2m.pid)
		sys.stderr.write('Started Moses m2c: %s\n' % self.pm2c.pid)
		sys.stderr.write('System ready.\n')
		sys.stderr.flush()
		self.taskqueue = []
		self.resultqueue = []

	def checkmoses(self, mode):
		if mode == "c2m":
			returncode = self.pc2m.poll()
			if returncode is not None:
				sys.stderr.write('Moses c2m (%s) is dead: %s\n' % (self.pc2m.pid, SIGNUM2NAME.get(-returncode, str(returncode))))
				self.pc2m.wait()
				self.pc2m = runmoses('c2m')
				sys.stderr.write('Restarted Moses c2m: %s\n' % self.pc2m.pid)
			return self.pc2m
		else:
			returncode = self.pm2c.poll()
			if returncode is not None:
				sys.stderr.write('Moses m2c (%s) is dead: %s\n' % (self.pm2c.pid, SIGNUM2NAME.get(-returncode, str(returncode))))
				self.pm2c.wait()
				self.pm2c = runmoses('m2c')
				sys.stderr.write('Restarted Moses m2c: %s\n' % self.pm2c.pid)
			return self.pm2c

	def tokenize(self, s, mode):
		if mode == "c2m":
			return ' '.join(zhutil.addwalls(map(xml_escape, filter(notwhite, jiebazhc.cut(s)))))
		else:
			return ' '.join(zhutil.addwalls(map(xml_escape, filter(notwhite, jieba.cut(s)))))

	def processtasks(self, mode):
		if not self.taskqueue:
			return True
		for sn, s in self.taskqueue:
			proc = self.checkmoses(mode)
			tok = self.tokenize(s, mode)
			proc.stdin.write(('%s\n' % tok).encode('utf8'))
		proc.stdin.flush()
		for sn, s in self.taskqueue:
			rv = detokenize(proc.stdout.readline().decode('utf8'))
			if not rv:
				return False
			self.resultqueue.append((sn, rv))
			self.lrucache.add((s, mode), rv)
			if mode == "c2m":
				self.sqlcache.add(s, rv)
		return True

	def getcache(self, text, mode):
		rv = self.lrucache.get((text, mode))
		if rv is None and mode == "c2m":
			rv = self.sqlcache.get(text)
		return rv

	def translate(self, text, mode, withcount=False):
		hitcount = 0
		misscount = 0
		snum = 0
		self.taskqueue = []
		self.resultqueue = []
		for l in text.split('\n'):
			sentences = zhutil.splithard(zhconv(l.strip(), 'zh-cn'), 128)
			for s in sentences:
				if s:
					crv = self.getcache(s, mode)
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
		self.processtasks(mode) # Error handling?
		self.resultqueue.sort()
		sys.stderr.write('%s Translated %s/%s sentences, %s.\n' % (time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime()), misscount, hitcount + misscount, mode))
		ig = itemgetter(1)
		outputtext = ''.join(map(ig, self.resultqueue))
		if withcount:
			return (outputtext, misscount)
		else:
			return outputtext

def handle(mm, data):
	oper = umsgpack.loads(data)
	if oper[0] == 'c2m':
		return umsgpack.dumps(mm.translate(oper[1], 'c2m', oper[2]))
	elif oper[0] == 'm2c':
		return umsgpack.dumps(mm.translate(oper[1], 'm2c', oper[2]))
	elif oper[0] == 'cut':
		return umsgpack.dumps(tuple(jieba.cut(*oper[1], **oper[2])))
	elif oper[0] == 'cut_for_search':
		return umsgpack.dumps(tuple(jieba.cut_for_search(*oper[1], **oper[2])))
	elif oper[0] == 'tokenize':
		return umsgpack.dumps(tuple(jieba.tokenize(*oper[1], **oper[2])))
	elif oper[0] == 'jiebazhc.cut':
		return umsgpack.dumps(tuple(jiebazhc.cut(*oper[1], **oper[2])))
	elif oper[0] == 'jiebazhc.cut_for_search':
		return umsgpack.dumps(tuple(jiebazhc.cut_for_search(*oper[1], **oper[2])))
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

def recvall(sock, buf=1024):
	data = sock.recv(buf)
	alldata = [data]
	while len(data) == buf:
		data = sock.recv(buf)
		alldata.append(data)
	return b''.join(alldata)

def receive(filename, data):
	sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
	sock.connect(filename)
	sock.sendall(data)
	received = recvall(sock, 1024)
	sock.close()
	return received

def serve(filename):
	mm = None
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
		with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sock:
			sock.bind(filename)
			sock.listen(5)
			jieba.initialize(DICT_SMALL)
			jiebazhc.initialize()
			mm = MosesManagerThread()
			while 1:
				conn, addr = sock.accept()
				received = recvall(conn, 1024)
				result = handle(mm, received)
				if result is None:
					conn.sendall(b"\xc0")
				elif result == b'stop':
					conn.sendall(b"\xc0")
					conn.close()
					break
				else:
					conn.sendall(result)
				conn.close()
	finally:
		if mm:
			mm.pc2m.terminate()
			mm.pm2c.terminate()
			mm.sqlcache.gc()
		if os.path.exists(filename):
			os.unlink(filename)
		print("Server stopped.")

if __name__ == '__main__':
	filename = MS_SOCK
	try:
		serve(filename)
	except OSError as ex:
		if 'Address already in use' in str(ex):
			print("Server already started.")

