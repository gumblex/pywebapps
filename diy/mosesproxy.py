#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import sys
import json
import socket
from subprocess import Popen
from config import *

_curpath = os.path.normpath(os.path.join(os.getcwd(), os.path.dirname(__file__)))
startserver_path = os.path.join(_curpath, 'startserver')

filename = MS_SOCK
autorestart = True

def receive(data):
	global filename
	sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
	try:
		sock.connect(filename)
	except (FileNotFoundError, ConnectionRefusedError) as ex:
		if autorestart:
			Popen(('/bin/bash', startserver_path)).wait()
			sock.connect(filename)
		else:
			raise ex
	sock.sendall(data)
	received = sock.recv(1024)
	if not received and autorestart:
		Popen(('/bin/bash', startserver_path)).wait()
		sock.sendall(data)
		received = sock.recv(1024)
	while received[-1] != 10:
		received += sock.recv(1024)
	sock.close()
	return received.decode('utf-8')

def translate(text, mode):
	return json.loads(receive(json.dumps((mode,text)).encode('utf-8') + b"\n"))

def cut(*args, **kwargs):
	return json.loads(receive(json.dumps(('cut',args,kwargs)).encode('utf-8') + b"\n"))

def cut_for_search(*args, **kwargs):
	return json.loads(receive(json.dumps(('cut_for_search',args,kwargs)).encode('utf-8') + b"\n"))

def tokenize(*args, **kwargs):
	return json.loads(receive(json.dumps(('tokenize',args,kwargs)).encode('utf-8') + b"\n"))

class jiebazhc:
	def cut(*args, **kwargs):
		return json.loads(receive(json.dumps(('jiebazhc.cut',args,kwargs)).encode('utf-8') + b"\n"))

	def cut_for_search(*args, **kwargs):
		return json.loads(receive(json.dumps(('jiebazhc.cut_for_search',args,kwargs)).encode('utf-8') + b"\n"))

	def tokenize(*args, **kwargs):
		return json.loads(receive(json.dumps(('jiebazhc.tokenize',args,kwargs)).encode('utf-8') + b"\n"))

def add_word(*args, **kwargs):
	receive(json.dumps(('add_word',args,kwargs)).encode('utf-8') + b"\n")

def load_userdict(*args):
	receive(json.dumps(('load_userdict',args)).encode('utf-8') + b"\n")

def set_dictionary(*args):
	receive(json.dumps(('set_dictionary',args)).encode('utf-8') + b"\n")

def stopserver():
	receive(json.dumps(('stopserver',)).encode('utf-8') + b"\n")

def ping():
	try:
		result = receive(json.dumps(('ping',)).encode('utf-8') + b"\n").strip()
		return result == 'pong'
	except:
		return False

if __name__ == '__main__':
	if len(sys.argv) > 1:
		if sys.argv[1] == 'stop':
			if ping():
				stopserver()
		elif sys.argv[1] == 'ping':
			if not ping():
				sys.exit(1)
	else:
		if not ping():
			sys.exit(1)
