#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import sys
import time
import itertools
import statistics
import mosesproxy2

data = []
mode = sys.argv[1]

while True:
    next_n_lines = ''.join(itertools.islice(sys.stdin, 100))
    if not next_n_lines:
        break
    timerec = time.time()
    try:
        mosesproxy2.translate(next_n_lines, mode)
    except KeyboardInterrupt:
        break
    data.append((time.time() - timerec) / len(next_n_lines))

dmax = max(data)
dmin = min(data)
mean = statistics.mean(data)
try:
    mode = statistics.mode(data)
except statistics.StatisticsError:
    mode = 0
median = statistics.median(data)
stdv = statistics.pstdev(data, mean)
print("dmax,dmin,mean,mode,median,stdv")
print(dmax, dmin, mean, mode, median, stdv)
