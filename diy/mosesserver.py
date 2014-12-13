#!/usr/bin/env python3
import sys, os
import re
import json
import subprocess
import configparser
import socket
from functools import lru_cache
from zhconv import convert as zhconv
from pangu import spacing
import zhutil
import jieba
import jiebazhc
from config import *

os.chdir(os.path.dirname(os.path.abspath(sys.argv[0])))
c2m = [MOSESBIN, '-f', MOSES_INI_c2m]
m2c = [MOSESBIN, '-f', MOSES_INI_m2c]
punct = frozenset(''':!),.:;?]}¢'"、。〉》」』】〕〗〞︰︱︳﹐､﹒﹔﹕﹖﹗﹚﹜﹞！），．：；？｜｝︴︶︸︺︼︾﹀﹂﹄﹏､～￠々‖•·ˇˉ―--′’”([{£¥'"‵〈《「『【〔〖（［｛￡￥〝︵︷︹︻︽︿﹁﹃﹙﹛﹝（｛“‘''')
longpunct = frozenset('-—_…')
whitespace = frozenset(' \t\n\r\x0b\x0c\u3000')

RE_WS_IN_FW = re.compile(r'([\u2018\u2019\u201c\u201d\u2e80-\u312f\u3200-\u32ff\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff\uff00-\uffef])\s+(?=[\u2018\u2019\u201c\u201d\u2e80-\u312f\u3200-\u32ff\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff\uff00-\uffef])')

detokenize = lambda s: spacing(RE_WS_IN_FW.sub(r'\1', s)).strip()

quiet = False
verbose = False
pm2c = subprocess.Popen(m2c, shell=False, stdin=subprocess.PIPE, stdout=subprocess.PIPE, cwd=os.getcwd())
pc2m = subprocess.Popen(c2m, shell=False, stdin=subprocess.PIPE, stdout=subprocess.PIPE, cwd=os.getcwd())

jieba.initialize()
sys.stderr.write('System ready.\n')
sys.stderr.flush()

def translate(text, mode):
	outputtext = []
	for l in text.split('\n'):
		outputtext.append('<p>')
		sentences = zhutil.splitsentence(zhconv(l.strip(), 'zh-hans'))
		for s in sentences:
			if mode == "c2m":
				proc = pc2m
				tok = ' '.join(filter(lambda x: x not in whitespace, jiebazhc.cut(s,cut_all=False)))
			else:
				proc = pm2c
				tok = ' '.join(filter(lambda x: x not in whitespace, jieba.cut(s,cut_all=False)))
			proc.stdin.write(('%s\n' % tok).encode('utf8'))
			proc.stdin.flush()
			outputtext.append(detokenize(proc.stdout.readline().decode('utf8')))
		outputtext.append('</p>\n')
	return ''.join(outputtext)

@lru_cache()
def handle(data):
	oper = json.loads(data)
	if oper[0] == 'c2m':
		return json.dumps(translate(oper[1], 'c2m')).encode('utf-8')
	elif oper[0] == 'm2c':
		return json.dumps(translate(oper[1], 'm2c')).encode('utf-8')
	elif oper[0] == 'stopserver':
		return b'stop'
	elif oper[0] == 'ping':
		return b'pong'

def receive(filename, data):
	sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
	sock.connect(filename)
	sock.sendall(data)
	received = sock.recv(1024)
	while received[-1] != 10:
		received += sock.recv(1024)
	sock.close()
	return received.decode('utf-8')

def serve(filename):
	if os.path.exists(filename):
		try:
			receive(filename, b'["ping"]\n')
			return
		except:
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
				received = conn.recv(1024)
				while received[-1] != 10:
					received += conn.recv(1024)
				result = handle(received.decode('utf-8'))
				if result is None:
					conn.sendall(b'\n')
				elif result == b'stop':
					conn.sendall(b'\n')
					conn.close()
					break
				else:
					conn.sendall(result + b'\n')
				conn.close()
	finally:
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

