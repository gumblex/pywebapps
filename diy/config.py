#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os

# Jieba small dict
DICT_SMALL = os.path.join(os.environ['OPENSHIFT_DATA_DIR'], "smalldict.txt")

# DB to store wordlist
DB_clozeword = os.path.join(os.environ['OPENSHIFT_DATA_DIR'], "cwordlist.db")

MOSESBIN = os.path.join(os.environ['OPENSHIFT_DATA_DIR'], "moses")
MOSES_CWD = os.environ['OPENSHIFT_DATA_DIR']
MOSES_INI_c2m = os.path.join(os.environ['OPENSHIFT_DATA_DIR'], "zhc2zhm", "moses.ini")
MOSES_INI_m2c = os.path.join(os.environ['OPENSHIFT_DATA_DIR'], "zhm2zhc", "moses.ini")

# Mosesserver socket
MS_SOCK = os.path.join(os.environ['OPENSHIFT_TMP_DIR'], "mosesserver.sock")

OS_ENV = os.environ
