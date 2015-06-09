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
from operator import itemgetter
from functools import lru_cache

import jieba
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

c2m = [MOSESBIN, '-v', '0', '-f', MOSES_INI_c2m,
       '--print-alignment-info'] + sys.argv[1:]
m2c = [MOSESBIN, '-v', '0', '-f', MOSES_INI_m2c,
       '--print-alignment-info'] + sys.argv[1:]

jiebazhc = jieba.Tokenizer(DICT_ZHC)
jiebazhc.cache_file = "jiebazhc.cache"

punct = frozenset(
    ''':!),.:;?]}¢'"、。〉》」』】〕〗〞︰︱︳﹐､﹒﹔'''
    '''﹕﹖﹗﹚﹜﹞！），．：；？｜｝︴︶︸︺︼︾﹀﹂﹄﹏､'''
    '''～￠々‖•·ˇˉ―--′’”([{£¥'"‵〈《「『【〔〖（［｛'''
    '''￡￥〝︵︷︹︻︽︿﹁﹃﹙﹛﹝（｛“‘'''
)
longpunct = frozenset('-—_…')
whitespace = frozenset(' \t\n\r\x0b\x0c\u3000')

RE_WS_IN_FW = re.compile(
    '([\u2018\u2019\u201c\u201d\u2026\u2e80-\u312f\u3200-\u32ff\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff\ufe30-\ufe57\uff00-\uffef])\\s+(?=[\u2018\u2019\u201c\u201d\u2026\u2e80-\u312f\u3200-\u32ff\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff\ufe30-\ufe57\uff00-\uffef])'
)

RE_FW = re.compile(
    '([\u2018\u2019\u201c\u201d\u2026\u2e80-\u312f\u3200-\u32ff\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff\ufe30-\ufe57\uff00-\uffef\U00020000-\U0002A6D6]+)')

RE_CTRL = re.compile("[\000-\037\ufeff]")

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
    # special characters in moses
    "&": "&amp;",   # escape escape
    "|": "&#124;",  # factor separator
    "<": "&lt;",    # xml
    ">": "&gt;",    # xml
    "'": "&apos;",  # xml
    '"': "&quot;",  # xml
    "[": "&#91;",   # syntax non-terminal
    "]": "&#93;",   # syntax non-terminal
}

xml_unescape_table = dict((v, k) for k, v in xml_escape_table.items())

mc = None

zhconv2s = lambda text: (zhconv(text, 'zh-hans')
                         .replace("「", "“")
                         .replace("」", "”")
                         .replace("『", "‘")
                         .replace("』", "’"))

zhconv2t = lambda text: (zhconv(text, 'zh-hant')
                         .replace("“", "「")
                         .replace("”", "」")
                         .replace("‘", "『")
                         .replace("’", "』"))


def xml_escape(text):
    """Produce entities within text."""
    return "".join(xml_escape_table.get(c, c) for c in text)


def xml_unescape(text):
    # This is a limited version only for entities defined in xml_escape_table
    for k, v in xml_unescape_table.items():
        text = text.replace(k, v)
    return text


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
        try:
            msg = handlemsg(recvall(self.request))
            if msg == b'stop':
                self.server.shutdown()
            elif msg:
                sendall(self.request, msg)
        except Exception as ex:
            sendall(self.request, umsgpack.dumps(repr(ex)))
            raise ex


class ThreadedUStreamServer(
        socketserver.ThreadingMixIn, socketserver.UnixStreamServer):
    pass


class Sentence:

    def __init__(self, s, t=None, align=None, ps=None):
        self.s = s   # original input
        self.ps = ps or s  # prepared source
        self.t = t or []
        self.align = align or []
        self.stok = None

    def __repr__(self):
        return 'Sentence(%r, t=%r, align=%r)' % (self.s, self.t, self.align)

    @staticmethod
    def eq(s):
        return Sentence(s, (s,))

    @staticmethod
    def eqa(s):
        return Sentence(s, (s,), (((0, len(s)),),))

dumptsentence = lambda s: umsgpack.dumps((s.t, s.align))
loadtsentence = lambda s, d: Sentence(s, *umsgpack.loads(d))
SNewline = Sentence.eq('\n')


class TranslateContext:

    def __init__(self, cache, tokenizer):
        self.sentences = []
        self.lrucache = cache
        self.tokenizer = tokenizer
        self.hitcount = 0
        self.misscount = 0

    def getcache(self, text):
        return self.lrucache.get(text)

    def prefilter(self, s):
        """No adding or removing characters."""
        return zhconv2s(zhutil.hw2fw(s.strip()))

    def postfilter(self, s):
        return xml_escape(' '.join(s.split()))

    def raw2moses(self, text):
        # Step 1: Filter, Cut sentences, Assign tasks
        for l in text.splitlines():
            sentences = zhutil.splithard(RE_CTRL.sub("", l.strip()), 80)
            for s in sentences:
                if any(0x4DFF < ord(ch) < 0x9FCD for ch in s):
                    ps = self.prefilter(s)
                    crv = self.getcache(ps)
                    if crv:
                        self.sentences.append(loadtsentence(s, crv))
                        self.hitcount += 1
                    else:
                        self.sentences.append(Sentence(s, ps=ps))
                        self.misscount += 1
                else:
                    self.sentences.append(Sentence.eq(s))
            self.sentences.append(SNewline)
        self.sentences.pop()

        # Step 2: Pre-process tasks, Convert to Moses input format
        needtrans = []
        for k, sent in enumerate(self.sentences):
            if sent.t:
                continue
            needtrans.append(k)
            start = 0
            tokens = []
            align = []
            for t in zhutil.RE_FW.split(sent.ps):
                tok = t.strip(zhutil.whitespace)
                if tok:
                    if zhutil.RE_FW.match(tok):
                        for tw, ws, we in self.tokenizer.tokenize(tok, HMM=False):
                            tokens.append(tw)
                            align.append((start + ws, start + we))
                    else:
                        ws = 0
                        for tw in tok.split(' '):
                            tokens.append(xml_escape(tw))
                            align.append(
                                (start + ws, start + ws + len(tw) + 1))
                            ws += len(tw) + 1
                start += len(t)
            sent.stok = align
            yield (k, ' '.join(zhutil.addwallzone(tokens)))

    def postrecv(self, text, key):
        sent = self.sentences[key]
        ttxtraw, alnraw = text.strip().split('|||')
        tkns = xml_unescape(ttxtraw.strip()).split(' ')
        for k, tok in enumerate(tkns[:-1]):
            if RE_FW.match(tok[-1]) and RE_FW.match(tkns[k + 1][0]):
                sent.t.append(tok)
            else:
                sent.t.append(tok + ' ')
        sent.t.append(tkns[-1])
        sent.align = [None] * len(sent.t)
        for align in alnraw.strip().split(' '):
            src, tgt = align.split('-')
            src = sent.stok[int(src)]
            tgt = int(tgt)
            if sent.align[tgt]:
                if sent.align[tgt][-1][1] == src[0]:
                    sent.align[tgt][-1] = (sent.align[tgt][-1][0], src[1])
                else:
                    sent.align[tgt].append(src)
            else:
                sent.align[tgt] = [src]
        self.lrucache.add(sent.ps, dumptsentence(sent))

    def tokenoutput(self):
        rawin = []
        tokout = []
        pos = 0
        for sent in self.sentences:
            rawin.append(sent.s)
            if sent.align:
                for k, tok in enumerate(sent.t):
                    if sent.align[k]:
                        tokaln = tuple((pos + ws, pos + we)
                                       for ws, we in sent.align[k])
                        if tokout and tokout[-1][1] == tokaln:
                            lastt, lasta = tokout.pop()
                            tokout.append((lastt + tok, tokaln))
                        else:
                            tokout.append((tok, tokaln))
                    else:
                        tokout.append((tok, None))
            else:
                tokout.extend((tok, None) for tok in sent.t)
            pos += len(sent.s)
        return ''.join(rawin), tokout

    def rawoutput(self):
        rawin = []
        tokout = []
        for sent in self.sentences:
            rawin.append(sent.s)
            tokout.extend(sent.t)
        return ''.join(rawin), ''.join(tokout)


class MosesManagerThread:

    def __init__(self, mode, lock):
        self.mode = mode
        if self.mode == "c2m":
            self.tokenizer = jiebazhc
        else:
            self.tokenizer = jieba.dt
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

    def translate(self, text, withcount=False, withinput=True, align=True):
        with self.lock:
            if not self.run:
                return
            proc = self.checkmoses()
            timestart = time.time()
            ctx = TranslateContext(self.lrucache, self.tokenizer)
            keys = []
            for k, sent in ctx.raw2moses(text):
                keys.append(k)
                proc.stdin.write(('%s\n' % sent).encode('utf8'))
            proc.stdin.flush()
            for k in keys:
                rv = proc.stdout.readline()
                if not rv:
                    return False
                rv = rv.rstrip(b'\n').decode('utf8')
                ctx.postrecv(rv, k)
            intxt, outtxt = ctx.tokenoutput() if align else ctx.rawoutput()
            sys.stderr.write('%s,%s,%s,%s,%s,%.6f\n' % (
                time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime()), self.mode,
                ctx.misscount, ctx.hitcount + ctx.misscount, len(text),
                time.time() - timestart))
            if withinput:
                return (intxt, outtxt, ctx.misscount) if withcount else (intxt, outtxt)
            else:
                return (outtxt, ctx.misscount) if withcount else outtxt

    def rawtranslate(self, text):
        proc = self.checkmoses()
        lines = text.splitlines()
        for s in lines:
            proc.stdin.write(('%s\n' % s).encode('utf8'))
        proc.stdin.flush()
        out = []
        for s in lines:
            rv = proc.stdout.readline().rstrip(b'\n').decode('utf8')
            out.append(rv)
        return '\n'.join(out)

    def shutdown(self):
        self.run = False
        self.proc.terminate()


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
        return umsgpack.dumps(mc.c2m.translate(*oper[1:]))
    elif oper[0] == 'm2c':
        return umsgpack.dumps(mc.m2c.translate(*oper[1:]))
    elif oper[0] == 'c2m.raw':
        return umsgpack.dumps(mc.c2m.rawtranslate(oper[1]))
    elif oper[0] == 'm2c.raw':
        return umsgpack.dumps(mc.m2c.rawtranslate(oper[1]))
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
    else:
        return umsgpack.dumps('Command not found')


def serve(filename):
    global mc
    if os.path.exists(filename):
        try:
            sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            sock.connect(filename)
            sendall(sock, umsgpack.dumps(('ping',)))
            assert recvall(sock) == b'pong'
            sock.close()
            print("Server already started.")
            return False
        except Exception as ex:
            # not removed socket
            print("Found abandoned socket: " + repr(ex))
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
