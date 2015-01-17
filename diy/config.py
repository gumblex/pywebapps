#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os

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
