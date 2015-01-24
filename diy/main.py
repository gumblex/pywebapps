import os
import re
import flask
import datetime
import gzip
import functools
import logging
import sqlite3
import mosesproxy
from werkzeug.contrib.cache import SimpleCache
from werkzeug.contrib.fixers import ProxyFix
from urllib.parse import urlsplit, urlunsplit
from sqlitecache import SqliteUserLog
from config import *
from zhutil import checktxttype

NOTLOCAL = (os.environ['OPENSHIFT_CLOUD_DOMAIN'] != 'LOCAL')

logging.basicConfig(filename=os.path.join(os.environ['OPENSHIFT_LOG_DIR'], "flask.log"), format='*** %(asctime)s %(levelname)s [in %(filename)s %(funcName)s]\n%(message)s', level=logging.WARNING)

app = flask.Flask(__name__)

if NOTLOCAL:
	app.wsgi_app = ProxyFix(app.wsgi_app, num_proxies=2)
	app.config['SERVER_NAME'] = 'gumble.tk'
	app.url_map.default_subdomain = 'app'
	#app.url_map.host_matching = True

app.secret_key = SECRETKEY

userlog = SqliteUserLog(DB_userlog, DB_userlog_maxcnt, DB_userlog_expire)
db_ts = sqlite3.connect(DB_testsent)
cur_ts = db_ts.cursor()

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

#@app.route("/")
@gzipped
@functools.lru_cache(maxsize=1)
def index():
	return flask.send_from_directory(os.path.join(app.root_path, 'static'), 'index.html')

#@app.route('/favicon.ico')
def favicon():
	return flask.send_from_directory(os.path.join(app.root_path, 'static'), 'favicon.ico', mimetype='image/vnd.microsoft.icon')

#@app.route("/", subdomain='glass')
@gzipped
@functools.lru_cache(maxsize=1)
def index_glass():
	return flask.send_from_directory(os.path.join(app.root_path, 'static/glass'), 'index.html')

#@app.route("/<path:filename>", subdomain='glass')
@gzipped
@functools.lru_cache(maxsize=25)
def file_glass(filename):
	return flask.send_from_directory(os.path.join(app.root_path, 'static/glass'), filename)

#@app.route("/translate/")
def translate_alias():
	return flask.redirect(flask.url_for('wenyan'))

#@app.route("/", subdomain='wenyan', methods=('GET', 'POST'))
#@app.route("/wenyan/", methods=('GET', 'POST'))
@gzipped
def wenyan():
	tinput = flask.request.form.get('input', '')
	#if flask.request.form.get('lang') == 'm2c':
	if checktxttype(tinput) == 'm':
		lang = 'm2c'
		ischecked = ('', ' checked')
	else:
		lang = 'c2m'
		ischecked = (' checked', '')
	ip = flask.request.remote_addr
	origcnt = userlog.count(ip)
	count = 0
	valid, num = wy_validate(ip, origcnt)
	if valid is True:
		origcnt = 0
		userlog.delete(ip)
		del flask.session['c']
	else:
		logging.warning('Captcha failed: %s, %s, %s' % (ip, valid, num))
	if not tinput:
		toutput = ''
	elif len(tinput) > MAX_CHAR:
		toutput = '<p class="error">文本过长，请切分后提交。</p>'
	elif valid is False:
		toutput = '<p class="error">回答错误，请重试。</p>'
	else:
		toutput, count = mosesproxy.translate(tinput, lang, True)
		userlog.add(ip, count)
	captcha = ''
	if origcnt + count > userlog.maxcnt:
		captcha = flask.Markup(wy_gencaptcha(num + 2))
	return flask.render_template('translate.html', action=flask.url_for('wenyan'), tinput=tinput, lang=lang, ischecked=ischecked, toutput=flask.Markup(toutput), captcha=captcha)

def wy_validate(ip, origcnt):
	if origcnt > userlog.maxcnt:
		allcap = flask.session.get('c')
		if not allcap:
			return (False, 4)
		for cap in allcap:
			try:
				get = int(flask.request.form.get(str(cap)))
				cur_ts.execute("SELECT type FROM sentences WHERE id = ?", (cap,))
				ans = cur_ts.fetchone()[0]
				if get != ans:
					return (False, len(allcap))
			except Exception:
				return (False, len(allcap))
		return (True, 0)
	else:
		return (None, 0)

def wy_gencaptcha(num):
	if not num:
		return ''
	num = min(num, 10)
	cur_ts.execute("SELECT id, sent FROM sentences ORDER BY RANDOM() LIMIT ?", (num,))
	got = cur_ts.fetchall()
	flask.session['c'] = tuple(i[0] for i in got)
	return flask.render_template('captcha.html', sentences=got)

RE_NOTA = re.compile(r'^a\s.+|.+\S\sa\s.+')

@functools.lru_cache(maxsize=16)
def clozeword_lookup(sql, replace):
	db_cloze = sqlite3.connect(DB_clozeword)
	cur_cloze = db_cloze.cursor()
	return tuple(cur_cloze.execute(sql, replace))

#@app.route("/", subdomain='clozeword')
#@app.route("/clozeword/")
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

app.add_url_rule('/', 'index', index)
app.add_url_rule('/favicon.ico', 'favicon', favicon)
app.add_url_rule("/", 'index_glass', index_glass, subdomain='glass')
app.add_url_rule("/<path:filename>", "file_glass", file_glass, subdomain='glass')
app.add_url_rule("/translate/", 'translate_alias', redirect_to="/wenyan/")
app.add_url_rule("/clozeword/", 'clozeword', clozeword)
if NOTLOCAL:
	app.add_url_rule("/", "wenyan", wenyan, methods=('GET', 'POST'), subdomain='wenyan')
	app.add_url_rule("/wenyan/", "wenyan", wenyan, methods=('GET', 'POST'), alias=True)
else:
	app.add_url_rule("/wenyan/", "wenyan", wenyan, methods=('GET', 'POST'))

if __name__ == "__main__":
	app.config['SERVER_NAME'] = None
	app.run(debug=True)
