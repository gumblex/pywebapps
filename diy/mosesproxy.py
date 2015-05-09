#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import sys
import umsgpack
import socket
from subprocess import Popen
from config import *

_curpath = os.path.normpath(os.path.join(os.getcwd(), os.path.dirname(__file__)))
startserver_path = os.path.join(_curpath, 'startserver')

filename = MS_SOCK

def recvall(sock, buf=1024):
	data = sock.recv(buf)
	alldata = [data]
	while data and data[-1] != 0xc1:
		data = sock.recv(buf)
		alldata.append(data)
	return b''.join(alldata)[:-1]


def sendall(sock, data):
	sock.sendall(data + b'\xc1')


def receive(data, autorestart=True):
	global filename
	sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
	try:
		sock.connect(filename)
		sendall(sock, data)
	except (FileNotFoundError, ConnectionRefusedError, BrokenPipeError) as ex:
		if autorestart:
			Popen(('/bin/bash', startserver_path)).wait()
			sock.connect(filename)
			sendall(sock, data)
		else:
			raise ex
	received = recvall(sock)
	if not received and autorestart:
		Popen(('/bin/bash', startserver_path)).wait()
		sendall(sock, data)
		received = recvall(sock)
	sock.close()
	return received

def translate(text, mode, withcount=False):
	return umsgpack.loads(receive(umsgpack.dumps((mode,text,withcount))))

def rawtranslate(text, mode, withcount=False):
	return umsgpack.loads(receive(umsgpack.dumps((mode+'.raw',text))))

def cut(*args, **kwargs):
	return umsgpack.loads(receive(umsgpack.dumps(('cut',args,kwargs))))

def cut_for_search(*args, **kwargs):
	return umsgpack.loads(receive(umsgpack.dumps(('cut_for_search',args,kwargs))))

def tokenize(*args, **kwargs):
	return umsgpack.loads(receive(umsgpack.dumps(('tokenize',args,kwargs))))

class jiebazhc:
	@staticmethod
	def cut(*args, **kwargs):
		return umsgpack.loads(receive(umsgpack.dumps(('jiebazhc.cut',args,kwargs))))

	@staticmethod
	def cut_for_search(*args, **kwargs):
		return umsgpack.loads(receive(umsgpack.dumps(('jiebazhc.cut_for_search',args,kwargs))))

	@staticmethod
	def tokenize(*args, **kwargs):
		return umsgpack.loads(receive(umsgpack.dumps(('jiebazhc.tokenize',args,kwargs))))

def add_word(*args, **kwargs):
	receive(umsgpack.dumps(('add_word',args,kwargs)))

def load_userdict(*args):
	receive(umsgpack.dumps(('load_userdict',args)))

def set_dictionary(*args):
	receive(umsgpack.dumps(('set_dictionary',args)))

def stopserver():
	receive(umsgpack.dumps(('stopserver',)), False)

def ping(autorestart=False):
	try:
		result = receive(umsgpack.dumps(('ping',)), autorestart)
		return result == b'pong'
	except Exception:
		return False

if __name__ == '__main__':
	if len(sys.argv) > 1:
		if sys.argv[1] == 'stop':
			if ping():
				stopserver()
		elif sys.argv[1] == 'ping':
			if not ping():
				sys.exit(1)
		elif sys.argv[1] == 'c2m':
			if not ping():
				sys.exit(1)
			sys.stdout.write(translate(sys.stdin.read(), 'c2m'))
		elif sys.argv[1] == 'm2c':
			if not ping():
				sys.exit(1)
			sys.stdout.write(translate(sys.stdin.read(), 'm2c'))
		elif sys.argv[1] == 'c2m.raw':
			if not ping():
				sys.exit(1)
			sys.stdout.write(translate(sys.stdin.read(), 'c2m.raw'))
		elif sys.argv[1] == 'm2c.raw':
			if not ping():
				sys.exit(1)
			sys.stdout.write(translate(sys.stdin.read(), 'm2c.raw'))
	else:
		if not ping():
			sys.exit(1)
