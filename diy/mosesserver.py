#!/usr/bin/env python3
import sys, os
import re
import umsgpack
import subprocess
import socket
import signal
import time
from functools import lru_cache
import resource

from zhconv import convert as zhconv
from pangu import spacing
import zhutil
import jieba
import jiebazhc
from sqlitecache import SqliteCache
from config import *

#_curpath = os.path.normpath(os.path.join(os.getcwd(), os.path.dirname(__file__)))
#TIMEOUT_path = os.path.join(_curpath, 'timeout')

os.chdir(os.path.dirname(os.path.abspath(sys.argv[0])))

SIGNUM2NAME = dict((k, v) for v, k in signal.__dict__.items() if v.startswith('SIG') and not v.startswith('SIG_'))

cache = SqliteCache(DB_zhccache, DB_zhccache_maxlen)

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

detokenize = lambda s: spacing(RE_WS_IN_FW.sub(r'\1', s)).strip()

quiet = False
verbose = False

runmoses = lambda mode: subprocess.Popen(m2c, shell=False, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=sys.stderr, cwd=MOSES_CWD) if mode=='m2c' else subprocess.Popen(c2m, shell=False, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=sys.stderr, cwd=MOSES_CWD)

jieba.initialize(DICT_SMALL)
jiebazhc.initialize()

class MosesManager:
	def __init__(self):
		self.pc2m = runmoses('c2m')
		self.pm2c = runmoses('m2c')
		sys.stderr.write('Started Moses c2m: %s\n' % self.pc2m.pid)
		sys.stderr.write('Started Moses m2c: %s\n' % self.pm2c.pid)
		sys.stderr.write('System ready.\n')
		sys.stderr.flush()
		self.lastupdatetime = 0
		self.timediff = 3600

	@lru_cache(maxsize=64)
	def translatesentence(self, s, mode):
		if time.time() - self.lastupdatetime > self.timediff:
			sys.stderr.write(time.strftime("# %Y-%m-%d %H:%M:%S\n", time.gmtime()))
			self.lastupdatetime = time.time()
		for j in range(5):
			if mode == "c2m":
				rv = cache.get(s)
				if rv:
					return (rv, 0)
				returncode = self.pc2m.poll()
				if returncode is not None:
					sys.stderr.write('Moses c2m (%s) is dead: %s\n' % (self.pc2m.pid, SIGNUM2NAME.get(-returncode, str(returncode))))
					self.pc2m.wait()
					self.pc2m = runmoses('c2m')
					sys.stderr.write('Restarted Moses c2m: %s\n' % self.pc2m.pid)
				proc = self.pc2m
				tok = ' '.join(zhutil.addwalls(filter(notwhite, jiebazhc.cut(s,cut_all=False))))
				#print(tok)
			else:
				returncode = self.pm2c.poll()
				if returncode is not None:
					sys.stderr.write('Moses m2c (%s) is dead: %s\n' % (self.pm2c.pid, SIGNUM2NAME.get(-returncode, str(returncode))))
					self.pm2c.wait()
					self.pm2c = runmoses('m2c')
					sys.stderr.write('Restarted Moses m2c: %s\n' % self.pm2c.pid)
				proc = self.pm2c
				tok = ' '.join(zhutil.addwalls(filter(notwhite, jieba.cut(s,cut_all=False))))
			proc.stdin.write(('%s\n' % tok).encode('utf8'))
			proc.stdin.flush()
			rv = detokenize(proc.stdout.readline().decode('utf8'))
			if rv:
				break
		if mode == "c2m":
			cache.add(s, rv)
			if time.time() - self.lastupdatetime > self.timediff:
				cache.gc()
		self.lastupdatetime = time.time()
		return (rv, 1)

	def translate(self, text, mode, withcount=False):
		outputtext = []
		nohitcount = 0
		for l in text.split('\n'):
			outputtext.append('<p>')
			sentences = zhutil.splitsentence(zhconv(l.strip(), 'zh-cn'))
			for s in sentences:
				res = ''
				# prevent mem explode
				for i in range(0, len(s), 128):
					rv, nohit = self.translatesentence(s[i:i+128], mode)
					res += rv
					nohitcount += nohit
				outputtext.append(res)
			outputtext.append('</p>\n')
		if withcount:
			return (''.join(outputtext), nohit)
		else:
			return ''.join(outputtext)

def handle(data):
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
	if os.path.exists(filename):
		try:
			receive(filename, umsgpack.dumps(('ping',)))
			return False
		except Exception:
			# not removed socket
			print("Found abandoned socket")
			os.unlink(filename)
	try:
		with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sock:
			sock.bind(filename)
			sock.listen(5)
			jieba.initialize()
			while 1:
				conn, addr = sock.accept()
				received = recvall(conn, 1024)
				result = handle(received)
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
		mm.pc2m.terminate()
		mm.pm2c.terminate()
		cache.gc()
		if os.path.exists(filename):
			os.unlink(filename)
		print("Server stopped.")

if __name__ == '__main__':
	filename = MS_SOCK
	try:
		mm = MosesManager()
		serve(filename)
	except OSError as ex:
		if 'Address already in use' in str(ex):
			print("Server already started.")

