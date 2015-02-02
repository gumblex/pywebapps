#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import re

OS_DATA = os.environ['OPENSHIFT_DATA_DIR']

SECRETKEY = b'\xc6\x89\xaa:MC\x0b\xa9g\x86+\xe6\x06/\x93\xbfF,ZXY"\xfc\xe3\xd5\xd8\xc7\xc5\xf5ed\xb8'

# Jieba small dict
DICT_SMALL = os.path.join(os.environ['OPENSHIFT_DATA_DIR'], "smalldict.txt")

# DB to store wordlist
DB_clozeword = os.path.join(os.environ['OPENSHIFT_DATA_DIR'], "cwordlist.db")
DB_zhccache = os.path.join(os.environ['OPENSHIFT_DATA_DIR'], "zhccache.db")
DB_zhccache_maxlen = 65536
DB_userlog = os.path.join(os.environ['OPENSHIFT_DATA_DIR'], "userlog.db")
DB_userlog_maxcnt = 200
DB_userlog_expire = 3600
DB_testsent = os.path.join(os.environ['OPENSHIFT_DATA_DIR'], "testsent.db")

MOSESBIN = os.path.join(os.environ['OPENSHIFT_DATA_DIR'], "moses")
MOSES_CWD = os.environ['OPENSHIFT_DATA_DIR']
MOSES_INI_c2m = os.path.join(os.environ['OPENSHIFT_DATA_DIR'], "zhc2zhm", "moses.ini")
MOSES_INI_m2c = os.path.join(os.environ['OPENSHIFT_DATA_DIR'], "zhm2zhc", "moses.ini")
MOSES_MAXMEM = 512000

MAX_CHAR = 2048

# Mosesserver socket
MS_SOCK = os.path.join(os.environ['OPENSHIFT_TMP_DIR'], "mosesserver.sock")

OS_ENV = os.environ

BANNEDIP = re.compile(
"""
183.136.133.*
220.181.55.*
101.226.4.*
180.153.235.*
122.143.15.*
27.221.20.*
202.102.85.*
61.160.224.*
112.25.60.*
182.140.227.*
221.204.14.*
222.73.144.*
61.240.144.*
113.17.174.*
125.88.189.*
120.52.18.*
218.30.118.*
101.226.169.*
182.118.20.*
182.118.25.*
101.226.168.*
182.118.21.*
101.226.167.*
101.226.166.*
101.226.168.*
182.118.22.*
117.40.253.180
119.147.146.*
58.60.12.*
113.142.9.*
125.39.52.*
59.54.55.251
121.14.95.*
183.62.126.*
112.95.240.*
222.73.75.245
222.73.76.253
222.82.219.238
222.202.96.*
142.54.160.154
120.24.239.37
110.166.246.133
""".strip().replace('.', r'\.').replace('*', r'\d+').replace('\n', '|')
)
