#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os
import json
import socket
import jieba


def handle(data):
    oper = json.loads(data)
    if oper[0] == 'cut':
        return json.dumps(tuple(jieba.cut(*oper[1], **oper[2]))).encode('utf-8')
    elif oper[0] == 'cut_for_search':
        return json.dumps(tuple(jieba.cut_for_search(*oper[1], **oper[2]))).encode('utf-8')
    elif oper[0] == 'tokenize':
        return json.dumps(tuple(jieba.tokenize(*oper[1], **oper[2]))).encode('utf-8')
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
    filename = '/tmp/jieba.sock'
    try:
        serve(filename)
    except OSError as ex:
        if 'Address already in use' in str(ex):
            print("Server already started.")
