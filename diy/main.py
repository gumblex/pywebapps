import os
import re
import flask
import datetime
import base64
import logging
import sqlite3
import mosesproxy
from werkzeug.contrib.cache import SimpleCache
from urllib.parse import urlsplit, urlunsplit
from config import *

jieba = mosesproxy
jiebazhc = mosesproxy.jiebazhc()

app = flask.Flask(__name__)
app.config['SERVER_NAME'] = 'gumble.tk'
app.url_map.default_subdomain = 'app'

# For debug use

logging.basicConfig(filename=os.path.join(os.environ['OPENSHIFT_LOG_DIR'], "flask.log"), format='*** %(asctime)s %(levelname)s [in %(filename)s %(funcName)s]\n%(message)s', level=logging.WARNING)

try:
	from jiebademo import jiebademo
	app.register_blueprint(jiebademo, url_prefix='/jiebademo')
except Exception:
	logging.exception("Import jiebademo failed.")

def url_for_other_page(query, page):
	return flask.url_for(flask.request.endpoint, q=base64.urlsafe_b64encode(query.encode('utf-8').rstrip(b'=')), p=page)

app.jinja_env.globals['url_for_other_page'] = url_for_other_page

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

@app.route("/")
def index():
	return flask.send_from_directory(os.path.join(app.root_path, 'static'), 'index.html')

@app.route('/favicon.ico')
def favicon():
	return flask.send_from_directory(os.path.join(app.root_path, 'static'), 'favicon.ico', mimetype='image/vnd.microsoft.icon')

@app.route("/", subdomain='glass')
def index_glass():
	return flask.send_from_directory(os.path.join(app.root_path, 'static/glass'), 'index.html')

@app.route("/<path:filename>", subdomain='glass')
def file_glass(filename):
	return flask.send_from_directory(os.path.join(app.root_path, 'static/glass'), filename)

@app.route("/wenyan/")
@app.route("/translate/")
def wenyan():
	tinput = flask.request.form.get('input', '')
	if flask.request.form.get('lang') == 'm2c':
		lang = 'm2c'
		ischecked = ('', ' checked')
	else:
		lang = 'c2m'
		ischecked = (' checked', '')
	toutput = mosesproxy.translate(tinput, lang)
	return flask.render_template('translate.html', lang=lang, ischecked=ischecked, toutput=flask.Markup(toutput))

RE_NOTA = re.compile(r'^a\s.+|.+\S\sa\s.+')

#@app.route("/", subdomain='clozeword')
@app.route("/clozeword/")
def clozeword():
	fl = flask.request.args.get('fl', '').lower()
	if not fl:
		return flask.render_template('clozeword.html', fl="", result="")
	res = []
	db_cloze = sqlite3.connect(DB_clozeword)
	cur_cloze = db_cloze.cursor()
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
			exe = cur_cloze.execute("SELECT * FROM wordlist WHERE (speech<>'' AND word LIKE ?)", (sqlchr,))
		else:
			exe = cur_cloze.execute("SELECT * FROM wordlist WHERE (speech=? AND word LIKE ?)", (sp + '.', sqlchr))
		for row in exe:
			res.append('<tr><td>%s</td><td>%s</td><td>%s</td></tr>' % row)
		res.append('</tbody></table></p><p>')
		if pr != 's':
			res.append('<a href="%s">&gt;&gt;查询包含以 %s 开头的单词的词组...</a></p>' % (flask.url_for('clozeword', fl=fl, sp=sp, pr='p'), fl))
	else:
		res.append('<p><h2>查询结果：</h2><table border="1"><tbody><tr class="hd"><th>词组</th><th>解释</th></tr>')
		exe = cur_cloze.execute("SELECT word,mean FROM wordlist WHERE (speech='' AND (word LIKE ? OR word LIKE ?))", (fl+"%", "% "+fl+"%"))
		if fl == 'a':
			for row in exe:
				if RE_NOTA.search(row['word']) is None:
					res.append('<tr><td>%s</td><td>%s</td></tr>' % row)
		else:
			for row in exe:
				res.append('<tr><td>%s</td><td>%s</td></tr>' % row)
		res.append('</tbody></table></p><p><a href="%s">&lt;&lt;返回单词列表...</a></p>' % flask.url_for('clozeword', fl=fl, sp=sp))
	return flask.render_template('clozeword.html', fl=fl, result=flask.Markup('\n'.join(res)))

if __name__ == "__main__":
	app.run(debug=True)
