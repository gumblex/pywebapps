#!/usr/bin/python3
# encoding=utf-8
import os
import re
import base64
import sqlite3
import hashlib
import logging
import functools
import figcaptcha
import mosesproxy2

import flask
import markupsafe

from zhconv import convert as zhconv
from sqlitecache import SqliteUserLog
from zhutil import calctxtstat, checktxttype
from config import *

bp_wenyan = flask.Blueprint('wenyan', __name__)


def get_wy_db():
    userlog = getattr(flask.g, 'userlog', None)
    if userlog is None:
        userlog = flask.g.userlog = SqliteUserLog(
            DB_userlog, DB_userlog_maxcnt, DB_userlog_expire)
    return userlog


def translateresult(result, convfunc):
    markup = []
    jsond = []
    nl = markupsafe.Markup('</p>\n<p>')
    for tok, pos in result:
        if tok == '\n':
            markup.append(nl)
        elif pos:
            markup.append(markupsafe.Markup('<span>%s</span>') % convfunc(tok))
            jsond.append(pos)
        else:
            markup.append(convfunc(tok))
    markup = markupsafe.Markup().join(markup)
                #.replace(markupsafe.Markup('<p></p>'), markupsafe.Markup('<p>&nbsp;</p>'))
    return (markupsafe.Markup('<p>%s</p>\n') % markup,
            markupsafe.Markup(flask.json.dumps(jsond, separators=(',', ':'))))


def linebreak(s):
	return markupsafe.Markup('<p>%s</p>\n') % markupsafe.Markup('</p>\n<p>').join(s.rstrip().split('\n'))


def wenyan():
    userlog = get_wy_db()
    tinput = flask.request.values.get('input', '')
    formgetlang = flask.request.values.get('lang')
    displaylang = flask.request.values.get('dl')
    if formgetlang == 'c2m':
        lang = 'c2m'
    elif formgetlang == 'm2c':
        lang = 'm2c'
    else:  # == auto
        cscore, mscore = calctxtstat(tinput)
        if cscore == mscore:
            lang = None
        elif checktxttype(cscore, mscore) == 'c':
            lang = 'c2m'
        else:
            lang = 'm2c'

    ip = flask.request.remote_addr
    accepttw = flask.g.get('accepttw')
    L = (lambda x: zhconv(x, 'zh-tw')) if accepttw else (lambda x: x)
    origcnt = userlog.count(ip)
    count = 0
    valid = wy_validate(ip, origcnt, userlog)
    talign = markupsafe.Markup('[]')
    if valid == 1:
        origcnt = 0
        userlog.delete(ip)
        userlog.commit()
    elif valid == 0:
        logging.warning('Captcha failed: %s' % ip)
    if not tinput:
        toutput = ''
    elif valid == 0:
        toutput = markupsafe.Markup(L('<p class="error">回答错误，请重试。</p>'))
    elif lang is None:
        toutput = linebreak(tinput)
    elif len(tinput) > MAX_CHAR * (CHAR_RATIO if lang == 'c2m' else 1):
        toutput = markupsafe.Markup(L('<p class="error">文本过长，请切分后提交。</p>'))
    else:
        tinput, tres, count = mosesproxy2.translate(
            tinput, lang, True, True, True)
        toutput, talign = translateresult(tres, L)
        try:
            userlog.add(ip, count)
        except sqlite3.OperationalError:
            pass
        userlog.commit()
    captcha = ''
    if origcnt + count > userlog.maxcnt:
        captcha = L(wy_gencaptcha())
    return flask.render_template(('translate_zhtw.html' if accepttw else 'translate.html'), tinput=tinput, toutput=toutput, talign=talign, captcha=markupsafe.Markup(captcha))


def wenyan_about():
    accepttw = flask.g.get('accepttw')
    return flask.render_template('translate_about_zhtw.html' if accepttw else 'translate_about.html')


def wy_validate(ip, origcnt, userlog):
    if origcnt > userlog.maxcnt:
        try:
            key = flask.request.values.get('cq', '').encode('ascii')
            ans = flask.request.values.get('ca', '').lower().encode('ascii')
            key2 = base64.urlsafe_b64encode(
                hashlib.pbkdf2_hmac('sha256', ans, SECRETKEY, 100))
            if key == key2:
                return 1
            else:
                return 0
        except Exception:
            logging.exception('captcha')
            return 0
    return None


def wy_gencaptcha():
    captcha = figcaptcha.combinecaptcha(
        figcaptcha.getcaptcha(2) for i in range(2))
    ask = figcaptcha.noise(captcha[0])
    ans = captcha[1].lower().encode('ascii')
    key = base64.urlsafe_b64encode(
        hashlib.pbkdf2_hmac('sha256', ans, SECRETKEY, 100)).decode('ascii')
    return flask.render_template('captcha.html', pic=ask, ans=key)

bp_wenyan.add_url_rule("/", 'wenyan', wenyan, methods=('GET', 'POST'))
bp_wenyan.add_url_rule(
        "/wenyan/", "wenyan", wenyan, methods=('GET', 'POST'), alias=True)
bp_wenyan.add_url_rule(
        "/wenyan/about", "wenyan_about", wenyan, methods=('GET', 'POST'), alias=True)
