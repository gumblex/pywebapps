#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import sys
import json
import socket

filename = '/tmp/jieba.sock'

def receive(data):
	global filename
	sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
	sock.connect(filename)
	sock.sendall(data)
	received = sock.recv(1024)
	while received[-1] != 10:
		received += sock.recv(1024)
	sock.close()
	return received.decode('utf-8')

def cut(*args, **kwargs):
	return json.loads(receive(json.dumps(('cut',args,kwargs)).encode('utf-8') + b"\n"))

def cut_for_search(*args, **kwargs):
	return json.loads(receive(json.dumps(('cut_for_search',args,kwargs)).encode('utf-8') + b"\n"))

def tokenize(*args, **kwargs):
	return json.loads(receive(json.dumps(('tokenize',args,kwargs)).encode('utf-8') + b"\n"))

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
