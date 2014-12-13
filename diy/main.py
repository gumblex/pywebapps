import os
import flask
import datetime
import base64
import logging
import sqlite3
from werkzeug.contrib.cache import SimpleCache
from config import *

app = flask.Flask(__name__)
app.config['SERVER_NAME'] = 'gumble.tk'
app.url_map.default_subdomain = 'app'

# For debug use

logging.basicConfig(filename=os.path.join(os.environ['OPENSHIFT_LOG_DIR'], "flask.log"), format='*** %(asctime)s %(levelname)s [in %(filename)s %(funcName)s]\n%(message)s', level=logging.WARNING)

def url_for_other_page(query, page):
	return flask.url_for(flask.request.endpoint, q=base64.urlsafe_b64encode(query.encode('utf-8').rstrip(b'=')), p=page)

app.jinja_env.globals['url_for_other_page'] = url_for_other_page

@app.route("/")
def index():
	return send_from_directory(os.path.join(app.root_path, 'static'), 'index.html')

@app.route('/favicon.ico')
def favicon():
	return send_from_directory(os.path.join(app.root_path, 'static'), 'favicon.ico', mimetype='image/vnd.microsoft.icon')


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
		res.append('<p><h2>查询结果：</h2><table border="1"><tbody><tr class="hd"><td>单词</td><td>词性</td><td>解释</td></tr>')
		if sp == 'un':
			exe = cur_cloze.execute("SELECT * FROM wordlist WHERE speech<>'' AND word LIKE ?", sqlchr)
		else:
			exe = cur_cloze.execute("SELECT * FROM wordlist WHERE speech=? AND word LIKE ?", (sp + '.', sqlchr))
		for row in exe:
			res.append('<tr><td>%s</td><td>%s</td><td>%s</td></tr>' % row)
		res.append('</tbody></table></p><p>')
		if pr != 's':
			res.append('<a href="%s">&gt;&gt;查询包含以 %s 开头的单词的词组...</a></p>' % (url_for('clozeword', fl=fl, sp=sp, pr='p'), fl))
	else:
		res.append('<p><h2>查询结果：</h2><table border="1"><tbody><tr class="hd"><td>词组</td><td>解释</td></tr>')
		exe = cur_cloze.execute("SELECT * FROM wordlist WHERE speech='' AND (word LIKE ? OR word LIKE ?", (fl+"%", "% "+fl+"%"))
		if fl == 'a':
			for row in exe:
				if RE_NOTA.search(row['word']) is None:
					res.append('<tr><td>%s</td><td>%s</td></tr>' % row)
		else:
			for row in exe:
				res.append('<tr><td>%s</td><td>%s</td></tr>' % row)
		res.append('</tbody></table></p><p><a href="%s">&lt;&lt;返回单词列表...</a></p>' % url_for('clozeword', fl=fl, sp=sp))
	return flask.render_template('clozeword.html', fl=fl, result=flask.Markup('\n'.join(res)))

if __name__ == "__main__":
	app.run(debug=True)
