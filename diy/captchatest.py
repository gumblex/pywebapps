#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sqlite3
import zhutil
from config import *

db_ts = sqlite3.connect(DB_testsent)
cur_ts = db_ts.cursor()

count = 0
correct = 0
delta = []

for sent, typ in cur_ts.execute("SELECT sent, type FROM sentences"):
    cscore, mscore = zhutil.calctxtstat(sent)
    delta.append(cscore - mscore)
    count += 1
    if cscore > mscore and typ == 0 or cscore < mscore and typ == 1:
        correct += 1

print('Correct/Count:', correct, count)
print('             :', correct / count)

mean = sum(delta) / len(delta)
stdev = (sum((x - mean)**2 for x in delta) / len(delta))**.5

print('Mean, Stdev  :', mean, stdev)
