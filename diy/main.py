#!/usr/bin/env python3
import os
import re
import time
import datetime
import gzip
import hashlib
import base64
import functools
import logging
import sqlite3
import zipfile
import flask
import mosesproxy
import figcaptcha
from bukadown import getbukaurl
from werkzeug.contrib.cache import SimpleCache
from werkzeug.contrib.fixers import ProxyFix
from urllib.parse import urlsplit, urlunsplit
from sqlitecache import SqliteUserLog
from zhconv import convert as zhconv
from zhutil import calctxtstat, checktxttype
from config import *

logging.basicConfig(filename=os.path.join(os.environ['OPENSHIFT_LOG_DIR'], "flask.log"), format='*** %(asctime)s %(levelname)s [in %(filename)s %(funcName)s]\n%(message)s', level=logging.WARNING)

app = flask.Flask(__name__)

if NOTLOCAL:
	app.wsgi_app = ProxyFix(app.wsgi_app, num_proxies=2)
	app.config['SERVER_NAME'] = 'gumble.tk'
	app.url_map.default_subdomain = 'app'

app.secret_key = SECRETKEY

try:
	from jiebademo import jiebademo
	app.register_blueprint(jiebademo, url_prefix='/jiebademo')
except Exception:
	logging.exception("Import jiebademo failed.")

def gzipped(f):
	@functools.wraps(f)
	def view_func(*args, **kwargs):
		@flask.after_this_request
		def zipper(response):
			accept_encoding = flask.request.headers.get('Accept-Encoding', '')

			if 'gzip' not in accept_encoding.lower():
				return response

			response.direct_passthrough = False

			if (response.status_code < 200 or
				response.status_code >= 300 or
				'Content-Encoding' in response.headers):
				return response
			response.data = gzip.compress(response.data)
			response.headers['Content-Encoding'] = 'gzip'
			response.headers['Vary'] = 'Accept-Encoding'
			response.headers['Content-Length'] = len(response.data)

			return response

		return f(*args, **kwargs)

	return view_func

# From django.utils.translation.trans_real.parse_accept_lang_header
accept_language_re = re.compile(r'''
        ([A-Za-z]{1,8}(?:-[A-Za-z]{1,8})*|\*)       # "en", "en-au", "x-y-z", "*"
        (?:\s*;\s*q=(0(?:\.\d{,3})?|1(?:.0{,3})?))? # Optional "q=1.00", "q=0.8"
        (?:\s*,\s*|$)                               # Multiple accepts per header.
        ''', re.VERBOSE)

def accept_language_zh_tw(lang_string):
	"""
	Parses the lang_string, which is the body of an HTTP Accept-Language
	header, and returns a list of (lang, q-value), ordered by 'q' values.
	"""
	result = {}
	pieces = accept_language_re.split(lang_string)
	if pieces[-1]:
		return None
	for i in range(0, len(pieces) - 1, 3):
		first, lang, priority = pieces[i : i + 3]
		if first:
			return None
		priority = priority and float(priority) or 1.0
		result[lang.lower()] = priority
	if result.get('zh-tw', 0) > result.get('zh-cn', 0):
		return True
	else:
		return False

#@app.before_request
def redirect_subdomain():
	urlparts = urlsplit(flask.request.url)
	if urlparts.netloc != 'app.gumble.tk':
		appname = urlparts.netloc.split('.')[0]
		urlparts_list = list(urlparts)
		urlparts_list[1] = 'app.gumble.tk'
		urlparts_list[2] = '/' + appname + urlparts_list[2]
		newurl = urlunsplit(urlparts_list)
		response = app.response_class('Moved to %s\n' % newurl, 301)
		response.headers['Location'] = newurl
		response.autocorrect_location_header = False
		return response

@app.before_request
def banip():
	if BANNEDIP.match(flask.request.remote_addr):
		flask.abort(403)


@gzipped
@functools.lru_cache(maxsize=1)
def index():
	return flask.send_from_directory(os.path.join(app.root_path, 'static'), 'index.html')


def favicon():
	return flask.send_from_directory(os.path.join(app.root_path, 'static'), 'favicon.ico', mimetype='image/vnd.microsoft.icon')


@gzipped
@functools.lru_cache(maxsize=1)
def index_glass():
	return flask.send_from_directory(os.path.join(app.root_path, 'static/glass'), 'index.html')


@gzipped
@functools.lru_cache(maxsize=25)
def file_glass(filename):
	return flask.send_from_directory(os.path.join(app.root_path, 'static/glass'), filename)


def translate_alias():
	return flask.redirect(flask.url_for('wenyan'))


def linebreak(s):
	return flask.Markup('<p>%s</p>\n') % flask.Markup('</p>\n<p>').join(s.rstrip().split('\n'))


def get_wy_db():
	userlog = getattr(flask.g, 'userlog', None)
	if userlog is None:
		userlog = flask.g.userlog = SqliteUserLog(DB_userlog, DB_userlog_maxcnt, DB_userlog_expire)
	return userlog


@app.teardown_appcontext
def close_connection(exception):
	userlog = getattr(flask.g, 'userlog', None)
	db_ts = getattr(flask.g, 'db_ts', None)
	if userlog is not None:
		userlog.close()
	if db_ts is not None:
		db_ts.close()


@gzipped
def wenyan():
	userlog = get_wy_db()
	tinput = flask.request.form.get('input', '')
	uncertain = False
	formgetlang = flask.request.form.get('lang')
	if formgetlang == 'c2m':
		lang = 'c2m'
	elif formgetlang == 'm2c':
		lang = 'm2c'
	else: # == auto
		cscore, mscore = calctxtstat(tinput)
		if cscore == mscore == 0:
			lang = None
		elif checktxttype(cscore, mscore) == 'c':
			lang = 'c2m'
		else:
			lang = 'm2c'
		if abs(cscore - mscore) < 45:
			if lang == 'c2m':
				uncertain = 'm2c'
			elif lang == 'm2c':
				uncertain = 'c2m'

	ip = flask.request.remote_addr
	accepttw = accept_language_zh_tw(flask.request.headers.get('Accept-Language', ''))
	L = (lambda x: zhconv(x, 'zh-tw')) if accepttw else (lambda x: x)
	origcnt = userlog.count(ip)
	count = 0
	valid = wy_validate(ip, origcnt, userlog)
	if valid == 1:
		origcnt = 0
		userlog.delete(ip)
	elif valid == 0:
		logging.warning('Captcha failed: %s' % ip)
	if not tinput:
		toutput = ''
	elif valid == 0:
		toutput = L('<p class="error">回答错误，请重试。</p>')
	elif lang is None:
		toutput = linebreak(tinput)
	elif len(tinput) > MAX_CHAR:
		toutput = L('<p class="error">文本过长，请切分后提交。</p>')
	else:
		toutput, count = mosesproxy.translate(tinput, lang, True)
		toutput = linebreak(L(toutput))
		userlog.add(ip, count)
	captcha = ''
	if origcnt + count > userlog.maxcnt:
		captcha = L(wy_gencaptcha())
	return flask.render_template(('translate_zhtw.html' if accepttw else 'translate.html'), tinput=tinput, uncertain=uncertain, toutput=flask.Markup(toutput), captcha=flask.Markup(captcha))


def wy_validate(ip, origcnt, userlog):
	if origcnt > userlog.maxcnt:
		try:
			key = flask.request.form.get('cq', '').encode('ascii')
			ans = flask.request.form.get('ca', '').lower().encode('ascii')
			key2 = base64.urlsafe_b64encode(hashlib.pbkdf2_hmac('sha256', ans, SECRETKEY, 100))
			if key == key2:
				return 1
			else:
				return 0
		except Exception:
			logging.exception('captcha')
			return 0
	return None


def wy_gencaptcha():
	captcha = figcaptcha.combinecaptcha(figcaptcha.getcaptcha(2) for i in range(2))
	ask = figcaptcha.noise(captcha[0])
	ans = captcha[1].lower().encode('ascii')
	key = base64.urlsafe_b64encode(hashlib.pbkdf2_hmac('sha256', ans, SECRETKEY, 100)).decode('ascii')
	return flask.render_template('captcha.html', pic=ask, ans=key)

RE_NOTA = re.compile(r'^a\s.+|.+\S\sa\s.+')

@functools.lru_cache(maxsize=16)
def clozeword_lookup(sql, replace):
	db_cloze = sqlite3.connect(DB_clozeword)
	cur_cloze = db_cloze.cursor()
	return tuple(cur_cloze.execute(sql, replace))


@gzipped
def clozeword():
	fl = flask.request.args.get('fl', '').lower()
	if not fl:
		return flask.render_template('clozeword.html', fl="", result="")
	res = []
	pr = flask.request.args.get('pr', '')
	sp = flask.request.args.get('sp', '').rstrip('.')
	if pr == 's':
		sqlchr = '%' + fl
	elif fl[0] == '-':
		sqlchr = '%' + fl[1:]
	else:
		sqlchr = fl + '%'
	if pr != 'p':
		res.append('<p><h2>查询结果：</h2><table border="1"><tbody><tr class="hd"><th>单词</th><th>词性</th><th>解释</th></tr>')
		if sp == 'un':
			exe = clozeword_lookup("SELECT * FROM wordlist WHERE (speech<>'' AND word LIKE ?)", (sqlchr,))
		else:
			exe = clozeword_lookup("SELECT * FROM wordlist WHERE (speech=? AND word LIKE ?)", (sp + '.', sqlchr))
		for row in exe:
			res.append('<tr><td>%s</td><td>%s</td><td>%s</td></tr>' % row)
		res.append('</tbody></table></p><p>')
		if pr != 's':
			res.append('<a href="%s">&gt;&gt;查询包含以 %s 开头的单词的词组...</a></p>' % (flask.url_for('clozeword', fl=fl, sp=sp, pr='p'), fl))
	else:
		res.append('<p><h2>查询结果：</h2><table border="1"><tbody><tr class="hd"><th>词组</th><th>解释</th></tr>')
		exe = clozeword_lookup("SELECT word,mean FROM wordlist WHERE (speech='' AND (word LIKE ? OR word LIKE ?))", (fl+"%", "% "+fl+"%"))
		if fl == 'a':
			for row in exe:
				if RE_NOTA.search(row[0]) is None:
					res.append('<tr><td>%s</td><td>%s</td></tr>' % row)
		else:
			for row in exe:
				res.append('<tr><td>%s</td><td>%s</td></tr>' % row)
		res.append('</tbody></table></p><p><a href="%s">&lt;&lt;返回单词列表...</a></p>' % flask.url_for('clozeword', fl=fl, sp=sp))
	return flask.render_template('clozeword.html', fl=fl, result=flask.Markup('\n'.join(res)))


@functools.lru_cache(maxsize=128)
def buka_lookup(sql, replace):
	db_buka = sqlite3.connect(DB_buka)
	cur_buka = db_buka.cursor()
	return tuple(cur_buka.execute(sql, replace))


def buka_renamef(cid, idx, title, ctype):
	if idx is not None:
		idx = str(idx)
		if title:
			return title
		else:
			if ctype == 0:
				return '第' + idx.zfill(3) + '话'
			elif ctype == 1:
				return '第' + idx.zfill(2) + '卷'
			elif ctype == 2:
				return '番外' + idx.zfill(2)
			else:
				return idx.zfill(3)
	else:
		return str(cid)


def buka_sortid(cid, idx, title, ctype):
	title = title or ''
	idx = idx or 0
	if ctype == 0:
		return (2, idx, title, cid)
	elif ctype == 1:
		return (1, idx, title, cid)
	elif ctype == 2:
		return (0, idx, title, cid)
	else:
		return (-1, idx, title, cid)


def genchaporder(comicid):
	d = {'author': '', #mangainfo/author
		 'discount': '0', 'favor': 0,
		 'finish': '0', #ismangaend/isend
		 'intro': '',
		 'lastup': '', #mangainfo/recentupdatename
		 'lastupcid': '', #Trim and lookup chapterinfo/fulltitle
		 'lastuptime': '', #mangainfo/recentupdatetime
		 'lastuptimeex': '', #mangainfo/recentupdatetime + ' 00:00:00'
		 'links': [], #From chapterinfo
		 'logo': '', #mangainfo/logopath
		 'logos': '', #mangainfo/logopath.split('-')[0]+'-s.jpg'
		 'name': '', #mangainfo/title
		 'popular': 9999999, 'populars': '10000000+', 'rate': '20',
		 'readmode': 50331648, 'readmode2': '0',
		 'recomctrlparam': '101696', 'recomctrltype': '1',
		 'recomdelay': '2000', 'recomenter': '', 'recomwords': '',
		 'res': [],
		 #'res': [{'cid': '0', #downloadview/cid
			#'csize': '4942', 'restype': '1'}]
		 'resupno': '0', 'ret': 0, 'upno': '0'}
	lst = buka_lookup('SELECT name, author, logo, finish, lastchap, lastuptime, lastup FROM comics WHERE mid = ?', (comicid,))[0]
	d['name'] = lst[0]
	d['author'] = lst[1]
	d['logo'] = lst[2]
	d['logos'] = lst[2]
	d['finish'] = str(lst[3])
	d['lastupcid'] = str(lst[4])
	d['lastuptime'] = time.strftime("%Y-%m-%d", time.gmtime(lst[5]))
	d['lastuptimeex'] = time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime(lst[5]))
	d['lastup'] = lst[6]
	chlst = buka_lookup('SELECT cid, idx, title, type FROM chapters WHERE mid = ?', (comicid,))
	for lst in chlst:
		d['links'].append({'cid': str(lst[0]), #chapterinfo/cid
						'idx': str(lst[1] or lst[0]), #chapterinfo/idx
						'ressupport': '7', 'size': '2000',
						'title': lst[2] or '', 'type': str(lst[3] or '0')})
		d['res'].append({'cid': str(lst[0]), 'csize': '2000', 'restype': '4'})
		d['res'].append({'cid': str(lst[0]), 'csize': '2000', 'restype': '2'})
		d['res'].append({'cid': str(lst[0]), 'csize': '2000', 'restype': '1'})
	return d


@functools.lru_cache(maxsize=16)
def getchaporder(comicid):
	z = zipfile.ZipFile(ZIP_bkchap)
	try:
		return z.read('chaporder/%s.dat' % comicid)
	except Exception:
		return None

@gzipped
def bukadown():
	func = flask.request.form.get('f') or flask.request.args.get('f')
	accepttw = accept_language_zh_tw(flask.request.headers.get('Accept-Language', ''))
	L = (lambda x: zhconv(x, 'zh-tw')) if accepttw else (lambda x: x)
	template = 'buka_zhtw.html' if accepttw else 'buka.html'
	errmsg = flask.render_template(template, msg=flask.Markup(L('<p class="error">参数错误。<a href="javascript:history.back()">按此返回</a></p>')))
	if not func:
		return flask.render_template(template)
	elif func == 'i':
		cname = flask.request.args.get('name')
		if not cname:
			return flask.render_template(template, sname=cname)
		if cname.isdigit():
			rv = buka_lookup("SELECT mid,name,author,lastchap,lastup,available FROM comics WHERE mid = ?", (cname,))
		else:
			rv = None
		mres = None
		sortfunc = lambda x: abs(len(cname) - len(x[1]))
		if rv:
			cinfo = rv[0]
		else:
			rv = buka_lookup("SELECT mid,name,author,lastchap,lastup,available FROM comics WHERE name LIKE ?", ('%%%s%%' % zhconv(cname, 'zh-hans'),))
			if not rv:
				return flask.render_template(template, msg=flask.Markup(L('<p class="error">未找到符合的漫画。</p>')), sname=cname)
			rv = sorted(rv, key=sortfunc)
			cinfo = rv[0]
			if len(rv) > 1:
				mres = [('?f=i&name=%s' % r[0], r[1]) for r in rv]
		rv = buka_lookup("SELECT cid,idx,title,type FROM chapters WHERE mid = ?", (cinfo[0],))
		chapsortid = dict((i[0], buka_sortid(*i)) for i in rv)
		sortfunc = lambda x: chapsortid[x[0]]
		chapters = [(i[0], L(buka_renamef(*i))) for i in rv]
		chapters.sort(key=sortfunc, reverse=True)
		return flask.render_template(template, sname=cname, multiresult=mres, cinfo=cinfo, chapters=chapters, mid=cinfo[0])
	elif func == 'u':
		comicid = flask.request.form.get('mid', '')
		if not comicid.isdigit():
			return errmsg
		comicid = int(comicid)
		rv = buka_lookup("SELECT cid,idx,title,type FROM chapters WHERE mid = ?", (comicid,))
		chapname = dict((i[0], (buka_sortid(*i), buka_renamef(*i))) for i in rv)
		chaps = sorted(map(int, filter(str.isdigit, flask.request.form.keys())), key=chapname.__getitem__, reverse=True)
		links = []
		for ch in chaps:
			rv = getbukaurl(comicid, ch)
			if rv:
				links.append((ch, chapname[ch][1], rv))
			else:
				links.append((ch, chapname[ch][1], ''))
		linklist = '\n'.join(i[2] for i in links)
		return flask.render_template(template, sname=comicid, links=links, linklist=linklist, mid=comicid)
	elif func == 'c':
		comicid = flask.request.args.get('mid', '')
		if not comicid.isdigit():
			return errmsg
		chaporder = getchaporder(comicid)
		if chaporder is None:
			flask.abort(404)
		return flask.Response(chaporder, mimetype="application/json", headers={"Content-Disposition": "attachment;filename=chaporder.dat"})
	else:
		return errmsg

def bukadownloader_zip():
	return flask.send_from_directory(OS_DATA, 'bukadownloader.zip')

TMPL403 = open(os.path.join(app.root_path, 'templates/e403.html'), 'rb').read()
TMPL404 = open(os.path.join(app.root_path, 'templates/e404.html'), 'rb').read()
TMPL500 = open(os.path.join(app.root_path, 'templates/e500.html'), 'rb').read()

@app.errorhandler(403)
def err403(error):
	return TMPL403, 403

@app.errorhandler(404)
def err404(error):
	return TMPL404, 404

@app.errorhandler(500)
def err500(error):
	return TMPL500, 500

app.add_url_rule('/', 'index', index)
app.add_url_rule('/favicon.ico', 'favicon', favicon)
app.add_url_rule("/", 'index_glass', index_glass, subdomain='glass')
app.add_url_rule("/<path:filename>", "file_glass", file_glass, subdomain='glass')
app.add_url_rule("/translate/", 'translate_alias', redirect_to="/wenyan/")
app.add_url_rule("/clozeword/", 'clozeword', clozeword)
app.add_url_rule("/buka/", 'bukadown', bukadown, methods=('GET', 'POST'))
app.add_url_rule("/buka/bukadownloader.zip", 'bukadownloader_zip', bukadownloader_zip)
if NOTLOCAL:
	app.add_url_rule("/", "wenyan", wenyan, methods=('GET', 'POST'), subdomain='wenyan')
	app.add_url_rule("/wenyan/", "wenyan", wenyan, methods=('GET', 'POST'), alias=True)
else:
	app.add_url_rule("/wenyan/", "wenyan", wenyan, methods=('GET', 'POST'))

if __name__ == "__main__":
	app.config['SERVER_NAME'] = None
	app.run(debug=True)
