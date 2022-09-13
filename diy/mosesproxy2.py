#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os
import sys
import json
from config import MS_ZMQ_URL

import zmq

_curpath = os.path.normpath(
    os.path.join(os.getcwd(), os.path.dirname(__file__)))

address = MS_ZMQ_URL

dumpsjson = lambda x: json.dumps(x).encode('utf-8')
loadsjson = lambda x: json.loads(x.decode('utf-8'))


def rpc_call(fn, *args, **kwargs):
    zmq_context = zmq.Context.instance()
    sock = zmq_context.socket(zmq.REQ)
    sock.connect(address)
    poller = zmq.Poller()
    poller.register(sock, zmq.POLLIN)
    sock.send(dumpsjson({'cmd': fn, 'args': args, 'kwargs': kwargs}))
    evts = poller.poll(120*1000)
    poller.unregister(sock)
    if evts:
        data = sock.recv()
        d = loadsjson(data)
        if 'result' in d:
            return d['result']
        raise RuntimeError(d['err'])
    raise TimeoutError


def receive(data):
    sock = zmq_context.socket(zmq.REQ)
    sock.connect(address)
    sock.send(data)
    received = sock.recv()
    return received


def translate(text, mode, withcount=False, withinput=True, align=True):
    return rpc_call(mode, text, withcount=withcount, withinput=withinput, align=align)


def rawtranslate(text, mode, withcount=False):
    return rpc_call(mode + '.raw', text)


def modelname():
    return rpc_call('modelname')


def cut(*args, **kwargs):
    return rpc_call('cut', *args, **kwargs)


def cut_for_search(*args, **kwargs):
    return rpc_call('cut_for_search', *args, **kwargs)


def tokenize(*args, **kwargs):
    return rpc_call('tokenize', *args, **kwargs)


class jiebazhc:

    @staticmethod
    def cut(*args, **kwargs):
        return rpc_call('jiebazhc.cut', *args, **kwargs)

    @staticmethod
    def cut_for_search(*args, **kwargs):
        return rpc_call('jiebazhc.cut_for_search', *args, **kwargs)

    @staticmethod
    def tokenize(*args, **kwargs):
        return rpc_call('jiebazhc.tokenize', *args, **kwargs)


def add_word(*args, **kwargs):
    rpc_call('add_word', *args, **kwargs)


def load_userdict(*args):
    rpc_call('load_userdict', *args)


def set_dictionary(*args):
    rpc_call('set_dictionary', *args)


def stopserver():
    rpc_call('stopserver')


def ping():
    try:
        result = rpc_call('ping')
        return result == 'pong'
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
            sys.stdout.write(translate(sys.stdin.read(), 'c2m', 0, 0, 0) + '\n')
        elif sys.argv[1] == 'm2c':
            if not ping():
                sys.exit(1)
            sys.stdout.write(translate(sys.stdin.read(), 'm2c', 0, 0, 0) + '\n')
        elif sys.argv[1] == 'c2m.raw':
            if not ping():
                sys.exit(1)
            sys.stdout.write(translate(sys.stdin.read(), 'c2m.raw') + '\n')
        elif sys.argv[1] == 'm2c.raw':
            if not ping():
                sys.exit(1)
            sys.stdout.write(translate(sys.stdin.read(), 'm2c.raw') + '\n')
        elif sys.argv[1] == 'modelname':
            if not ping():
                sys.exit(1)
            sys.stdout.write((modelname() or '') + '\n')
    else:
        if not ping():
            sys.exit(1)
