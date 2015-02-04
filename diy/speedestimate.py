#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import math
import time
import re
from config import NOTLOCAL

EPSILON = 0.0000001
LOGDIR = os.environ['OPENSHIFT_LOG_DIR']
JSFILE = os.path.join(os.environ['OPENSHIFT_REPO_DIR'], 'diy/static/wenyan_.js')
JSWRITETO = JSFILE[:-4] + '.js'

if not NOTLOCAL:
	LOGDIR = os.path.join(LOGDIR, '../server/logs')

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
re_js = re.compile(r'(var k =) \d+(, b =) \d+')

def parselog(fromtime):
	logfile = os.path.join(LOGDIR, 'mosesserver.log')
	fromtime = time.strptime(fromtime, '%Y-%m-%d %H:%M:%S')
	validline = []
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
			validline.append((realchar, usedtime))
	if validline:
		lr = SimpleLinearRegression(validline)
		if lr.run():
			return (int(lr.b*1000), int(lr.a*1000))
	return None


def editjs(value, jsfile=JSFILE, writeto=''):
	if not writeto:
		writeto = jsfile
	f = open(jsfile, 'r').read()
	f = re_js.sub(r'\1 %s\2 %s' % value, f)
	with open(writeto, 'w') as w:
		w.write(f)


if __name__ == '__main__':
	editjs(parselog('2015-02-01 14:09:16'), JSFILE, JSWRITETO)
