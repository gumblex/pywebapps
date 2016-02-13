#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import re
import math
import time
import json

from config import NOTLOCAL

EPSILON = 0.0000001
LOGDIR = os.environ['OPENSHIFT_LOG_DIR']

if not NOTLOCAL:
    LOGDIR = os.path.join(LOGDIR, '../server/logs')

jswriteto = lambda s: s[:-4] + '.js'
_curpath = os.path.normpath(
    os.path.join(os.getcwd(), os.path.dirname(__file__)))


class SimpleLinearRegression:

    """ tool class as help for calculating a linear function """

    def __init__(self, data):
        """ initializes members with defaults """
        self.data = data  # list of (x,y) pairs
        self.a = 0        # "a" of y = a + b*x
        self.b = 0        # "b" of y = a + b*x
        self.r = 0        # coefficient of correlation

    def run(self):
        """ calculates coefficient of correlation and
                the parameters for the linear function """
        sumX, sumY, sumXY, sumXX, sumYY = 0, 0, 0, 0, 0
        n = float(len(self.data))

        for x, y in self.data:
            sumX += x
            sumY += y
            sumXY += x * y
            sumXX += x * x
            sumYY += y * y

        denominator = math.sqrt(
            (sumXX - 1 / n * sumX ** 2) * (sumYY - 1 / n * sumY ** 2))
        if denominator < EPSILON:
            return False

        # coefficient of correlation
        self.r = (sumXY - 1 / n * sumX * sumY)
        self.r /= denominator

        # is there no relationship between 'x' and 'y'?
        if abs(self.r) < EPSILON:
            return False

        # calculating 'a' and 'b' of y = a + b*x
        self.b = sumXY - sumX * sumY / n
        self.b /= (sumXX - sumX ** 2 / n)

        self.a = sumY - self.b * sumX
        self.a /= n
        return True

    def function(self, x):
        """ linear function (be aware of current
                coefficient of correlation """
        return self.a + self.b * x

    def __repr__(self):
        """ current linear function for print """
        return "y = f(x) = %(a)f + %(b)f*x" % self.__dict__

re_log = re.compile(r'^(.+?),(.+?),(\d+),(\d+),(\d+),(.+)$')
re_js = re.compile(r'(var kc =) \d+(, bc =) \d+(, km =) \d+(, bm =) \d+')

striplines = lambda s: '\n'.join(l.strip() for l in s.splitlines())


def parselog(fromtime):
    logfile = os.path.join(LOGDIR, 'mosesserver.log')
    fromtime = time.strptime(fromtime, '%Y-%m-%d %H:%M:%S')
    validlinec = []
    validlinem = []
    with open(logfile, 'r') as f:
        for ln in f:
            l = ln.strip()
            m = re_log.match(l)
            if not m:
                continue
            if time.strptime(m.group(1), '%Y-%m-%d %H:%M:%S') < fromtime:
                continue
            realchar = int(m.group(5)) * int(m.group(3)) / float(m.group(4))
            usedtime = float(m.group(6))
            if m.group(2) == 'c2m':
                validlinec.append((realchar, usedtime))
            else:
                validlinem.append((realchar, usedtime))
    lrc = SimpleLinearRegression(validlinec)
    lrm = SimpleLinearRegression(validlinem)
    kc, bc, km, bm = 28, 8883, 28, 8883
    if lrc.run():
        kc, bc = int(lrc.b * 1000), int(lrc.a * 1000)
    if lrm.run():
        km, bm = int(lrm.b * 1000), int(lrm.a * 1000)
    return kc, bc, km, bm

# min: -24.219574739049666

joinlist = lambda l: ''.join(chr(32 + int(-n * 3.9))
                             for n in l).replace('\\', '\\\\').replace('"', r'\"')


def writejs(value, jsfile):
    writeto = jswriteto(jsfile)
    js_zhdetect = 'var zhcmodel = "%s";\nvar zhmmodel = "%s";\n%s'
    zhcmodel = json.load(open(os.path.join(_curpath, 'modelzhc.json'), 'r'))
    zhmmodel = json.load(open(os.path.join(_curpath, 'modelzhm.json'), 'r'))
    f = striplines(js_zhdetect % (
        joinlist(zhcmodel), joinlist(zhmmodel),
        re_js.sub(r'\1 %s\2 %s\3 %s\4 %s' % value, open(jsfile, 'r').read())
    )) + '\n'
    with open(writeto, 'w') as w:
        w.write(f)

if __name__ == '__main__':
    REPODIR = os.environ['OPENSHIFT_REPO_DIR']
    writejs(parselog('2015-08-27 13:58:56'),
            os.path.join(REPODIR, 'diy/static/wenyan_.js'))
