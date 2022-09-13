#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import re

NOTLOCAL = (os.environ['OPENSHIFT_CLOUD_DOMAIN'] != 'LOCAL')

OS_DATA = os.environ['OPENSHIFT_DATA_DIR']

SECRETKEY = open(os.path.join(OS_DATA, "seckey.bin"), 'rb').read()

# Jieba small dict
DICT_SMALL = os.path.join(OS_DATA, "smalldict.txt")
DICT_ZHC = os.path.join(OS_DATA, "zhcdict.txt")

# DB to store wordlist
DB_clozeword = os.path.join(OS_DATA, "cwordlist.db")
DB_zhccache = os.path.join(OS_DATA, "zhccache.db")
DB_zhccache_maxlen = 65536
DB_userlog = os.path.join(OS_DATA, "userlog.db")
DB_userlog_maxcnt = 200
DB_userlog_expire = 3600
DB_testsent = os.path.join(OS_DATA, "testsent.db")

MODEL_name = os.path.join(OS_DATA, "namemodel.m")

DB_buka = os.path.join(OS_DATA, "buka.db")
DB_bukacache = os.path.join(OS_DATA, "bukacache.db")
ZIP_bkchap = os.path.join(OS_DATA, "chaporder.zip")

MOSESBIN = os.path.join(OS_DATA, "moses")
MOSES_CWD = OS_DATA
MOSES_INI_c2m = os.path.join(OS_DATA, "zhc2zhm", "moses.ini")
MOSES_INI_m2c = os.path.join(OS_DATA, "zhm2zhc", "moses.ini")
MOSES_MAXMEM = 512000

MAX_CHAR = 4000
CHAR_RATIO = 0.6643902034970293

# Mosesserver socket
sockvar = os.environ['OPENSHIFT_MS_SOCK'].split(':')
MS_SOCK = (sockvar[0], int(sockvar[1]))
MS_ZMQ_URL = os.environ.get('OPENSHIFT_MS_ZMQ_URL', 'tcp://127.0.0.1:13333')

OS_ENV = os.environ

BANNEDIP = re.compile(
    '|'.join(filter(lambda x: x[:1].isdigit(), open(os.path.join(OS_DATA, "banip.txt")).read().strip().replace('.', r'\.').replace('*', r'\d+').splitlines())))
