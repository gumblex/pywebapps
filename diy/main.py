#!/usr/bin/env python3
import os
import re
import time
import gzip
import random
import logging
import sqlite3
import zipfile
import datetime
import functools

import flask
import markov
import umsgpack
import chinesename
from bukadown import getbukaurl
from cachelib import SimpleCache
from urllib.parse import urlsplit, urlunsplit
from zhconv import convert as zhconv
from config import *

class FrontFix(object):
    """Fix IP and Host problems.

    :param app: the WSGI application
    """

    def __init__(self, app):
        self.app = app

    def __call__(self, environ, start_response):
        getter = environ.get
        forwarded_proto = getter('HTTP_X_FORWARDED_PROTO', '')
        forwarded_cfip = getter('HTTP_CF_CONNECTING_IP', '')
        forwarded_host = getter('HTTP_X_FORWARDED_HOST', '')
        http_host = getter('HTTP_HOST')
        environ.update({
            'werkzeug.proxy_fix.orig_wsgi_url_scheme':  getter('wsgi.url_scheme'),
            'werkzeug.proxy_fix.orig_remote_addr':      getter('REMOTE_ADDR'),
            'werkzeug.proxy_fix.orig_http_host':        http_host
        })
        if forwarded_cfip:
            environ['REMOTE_ADDR'] = forwarded_cfip
        if forwarded_host:
            http_host = forwarded_host
        # Fix subdomain matching here
        if http_host.endswith('gumble.pw'):
            environ['HTTP_HOST'] = http_host
        else:
            environ['HTTP_HOST'] = 'app.gumble.pw'
            environ['single_domain'] = 1
        if forwarded_proto:
            environ['wsgi.url_scheme'] = forwarded_proto
        return self.app(environ, start_response)

logging.basicConfig(filename=os.path.join(os.environ[
                    'OPENSHIFT_LOG_DIR'], "flask.log"), format='*** %(asctime)s %(levelname)s [in %(filename)s %(funcName)s]\n%(message)s', level=logging.WARNING)

app = flask.Flask(__name__)

app.wsgi_app = FrontFix(app.wsgi_app)
app.config['SERVER_NAME'] = 'gumble.pw'
app.url_map.default_subdomain = 'app'

app.secret_key = SECRETKEY

try:
    from jiebademo import jiebademo as bp_jiebademo
    app.register_blueprint(bp_jiebademo, url_prefix='/jiebademo')
except Exception:
    logging.exception("Import jiebademo failed.")

try:
    from wenyan import bp_wenyan, wenyan as wenyan_view, wenyan_about
    #app.register_blueprint(bp_wenyan, url_prefix='/wenyan')
except Exception:
    logging.exception("Import wenyan failed.")


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


def accept_language(lang_string):
    """
    Parses the lang_string, which is the body of an HTTP Accept-Language
    header, and returns a list of (lang, q-value), ordered by 'q' values.
    """
    result = {}
    pieces = accept_language_re.split(lang_string)
    if pieces[-1]:
        return None
    for i in range(0, len(pieces) - 1, 3):
        first, lang, priority = pieces[i: i + 3]
        if first:
            return None
        priority = priority and float(priority) or 1.0
        result[lang.lower()] = priority
    return result


def redirect_subdomain():
    urlparts = urlsplit(flask.request.url)
    if urlparts.netloc != 'app.gumble.pw':
        appname = urlparts.netloc.split('.')[0]
        urlparts_list = list(urlparts)
        urlparts_list[1] = 'app.gumble.pw'
        urlparts_list[2] = '/' + appname + urlparts_list[2]
        newurl = urlunsplit(urlparts_list)
        response = app.response_class('Moved to %s\n' % newurl, 301)
        response.headers['Location'] = newurl
        response.autocorrect_location_header = False
        return response


@app.before_request
def before_req():
    if BANNEDIP.match(flask.request.remote_addr):
        flask.abort(403)
    flask.g.singledomain = not flask.request.headers.get('Host', '').endswith('.gumble.pw')
    displaylang = flask.request.values.get('dl')
    acceptlang = accept_language(
        flask.request.headers.get('Accept-Language', '')) or {}
    if displaylang in ('zht', 'zh-tw', 'zh-hant'):
        acceptlang['zh-tw'] = 100
    elif displaylang in ('zhs', 'zh-cn', 'zh-hans'):
        acceptlang['zh-cn'] = 100
    else:
        acceptlang[displaylang] = 100
    flask.g.gzipped = gzipped
    flask.g.acceptlang = acceptlang
    flask.g.accepttw = (acceptlang.get('zh-tw', 0) > acceptlang.get('zh-cn', 0))


def index():
    return flask.send_from_directory(os.path.join(app.root_path, 'static'), 'index.html')


def favicon():
    return flask.send_from_directory(os.path.join(app.root_path, 'static'), 'favicon.ico', mimetype='image/vnd.microsoft.icon')


def generate_204():
    return flask.Response(status=204)


@functools.lru_cache(maxsize=1)
def index_glass():
    return flask.send_from_directory(os.path.join(app.root_path, 'static/glass'), 'index.html')


@functools.lru_cache(maxsize=25)
def file_glass(filename):
    return flask.send_from_directory(os.path.join(app.root_path, 'static/glass'), filename)


def redirect_wenyan_to_subdomain():
    return wenyan_view()

def linebreak(s):
    return flask.Markup('<p>%s</p>\n') % flask.Markup('</p>\n<p>').join(s.rstrip().split('\n'))


def option_dict(v):
    return {v: ' selected'}


@app.teardown_appcontext
def close_connection(exception):
    userlog = getattr(flask.g, 'userlog', None)
    db_cloze = getattr(flask.g, 'db_cloze', None)
    db_buka = getattr(flask.g, 'db_buka', None)
    if userlog is not None:
        userlog.close()
    if db_cloze is not None:
        db_cloze.close()
    if db_buka is not None:
        db_buka.close()


RE_NOTA = re.compile(r'^a\s.+|.+\S\sa\s.+')


@functools.lru_cache(maxsize=16)
def clozeword_lookup(sql, replace):
    db_cloze = getattr(flask.g, 'db_cloze', None)
    if db_cloze is None:
        db_cloze = flask.g.db_cloze = sqlite3.connect(DB_clozeword)
    cur_cloze = db_cloze.cursor()
    return tuple(cur_cloze.execute(sql, replace))


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
        res.append(
            '<p><h2>查询结果：</h2><table border="1" class="table"><tbody><tr class="hd"><th>单词</th><th>词性</th><th>解释</th></tr>')
        if sp == 'un':
            exe = clozeword_lookup(
                "SELECT * FROM wordlist WHERE (speech<>'' AND word LIKE ?)", (sqlchr,))
        else:
            exe = clozeword_lookup(
                "SELECT * FROM wordlist WHERE (speech=? AND word LIKE ?)", (sp + '.', sqlchr))
        for row in exe:
            res.append('<tr><td>%s</td><td>%s</td><td>%s</td></tr>' % row)
        res.append('</tbody></table></p><p>')
        if pr != 's':
            res.append('<a href="%s">&gt;&gt;查询包含以 %s 开头的单词的词组...</a></p>' %
                       (flask.url_for('clozeword', fl=fl, sp=sp, pr='p'), fl))
    else:
        res.append(
            '<p><h2>查询结果：</h2><table border="1" class="table"><tbody><tr class="hd"><th>词组</th><th>解释</th></tr>')
        exe = clozeword_lookup(
            "SELECT word,mean FROM wordlist WHERE (speech='' AND (word LIKE ? OR word LIKE ?))", (fl + "%", "% " + fl + "%"))
        if fl == 'a':
            for row in exe:
                if RE_NOTA.search(row[0]) is None:
                    res.append('<tr><td>%s</td><td>%s</td></tr>' % row)
        else:
            for row in exe:
                res.append('<tr><td>%s</td><td>%s</td></tr>' % row)
        res.append('</tbody></table></p><p><a href="%s">&lt;&lt;返回单词列表...</a></p>' %
                   flask.url_for('clozeword', fl=fl, sp=sp))
    return flask.render_template('clozeword.html', fl=fl, result=flask.Markup('\n'.join(res)))


@functools.lru_cache(maxsize=25)
def select_name(userinput, num):
    namemodel = getattr(flask.g, 'namemodel', None)
    if namemodel is None:
        namemodel = flask.g.namemodel = chinesename.NameModel(MODEL_name)
    return namemodel.processinput(userinput, num)


def name_generator():
    accepttw = flask.g.get('accepttw')
    L = (lambda x: zhconv(x, 'zh-tw')) if accepttw else (lambda x: x)
    c = zhconv(flask.request.args.get('c', ''), 'zh-cn')
    sp = rawsp = flask.request.args.get('sp', ', ')
    if sp == 'br':
        sp = flask.Markup('<br>')
    try:
        num = int(flask.request.args.get('num', 100))
    except Exception:
        num = 100
    fjson = flask.request.headers.get('X-Requested-With') == 'XMLHttpRequest' or flask.request.args.get('f') == "json"
    if c:
        surnames, names = select_name(c, num)
    else:
        namemodel = getattr(flask.g, 'namemodel', None)
        if namemodel is None:
            namemodel = flask.g.namemodel = chinesename.NameModel(MODEL_name)
        surnames, names = namemodel.processinput(c, num)
    if fjson:
        return flask.jsonify({'s': list(map(L, surnames)), 'n': list(map(L, names))})
    else:
        tmpl = flask.render_template('name.html', c=c, surnames=sp.join(surnames), names=sp.join(names))
        if accepttw:
            tmpl = zhconv(tmpl.replace('zh-cn', 'zh-tw'), 'zh-tw')
        return tmpl


def username_generator():
    mkv_lvl = 310
    mkv_len = 16
    acceptlang = flask.g.get('acceptlang')
    accepttw = flask.g.get('accepttw')
    try:
        num = int(flask.request.args.get('num', 100))
    except Exception:
        num = 100
    fjson = flask.request.headers.get('X-Requested-With') == 'XMLHttpRequest' or flask.request.args.get('f') == "json"
    unamemodel = getattr(flask.g, 'unamemodel', None)
    if unamemodel is None:
        unamemodel = flask.g.unamemodel = markov.MarkovModel(
            os.path.join(OS_DATA, 'stats_user.txt'))
        cachefn = os.path.join(OS_DATA, 'stats_user_%d-%d.msgp' % (mkv_lvl, mkv_len))
        if os.path.isfile(cachefn):
            with open(cachefn, 'rb') as f:
                nbparts = umsgpack.load(f)
            idxrange = unamemodel.init(mkv_lvl, mkv_len, nbparts)
        else:
            idxrange = unamemodel.init(mkv_lvl, mkv_len)
            with open(cachefn, 'wb') as f:
                umsgpack.dump(unamemodel.nbparts, f)
    else:
        idxrange = unamemodel[(0, 0, 0)]
    names = [unamemodel.print_pwd(random.randrange(idxrange))[0] for x in range(num)]
    if fjson:
        return flask.jsonify({'usernames': names})
    uselang = (max(('en', 'zh-cn', 'zh-tw', 'zh'), key=lambda x: acceptlang.get(x, 0)) if acceptlang else 'en')
    if uselang.startswith('zh'):
        if uselang == 'zh-tw':
            tmpl = flask.render_template('username_zhtw.html', usernames=names)
        else:
            tmpl = flask.render_template('username_zhcn.html', usernames=names)
    else:
        tmpl = flask.render_template('username_en.html', usernames=names)
    return tmpl


@functools.lru_cache(maxsize=128)
def buka_lookup(sql, replace):
    db_buka = getattr(flask.g, 'db_buka', None)
    if db_buka is None:
        db_buka = flask.g.db_buka = sqlite3.connect(DB_buka)
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
    d = {'author': '',  # mangainfo/author
         'discount': '0', 'favor': 0,
         'finish': '0',  # ismangaend/isend
         'intro': '',
         'lastup': '',  # mangainfo/recentupdatename
         'lastupcid': '',  # Trim and lookup chapterinfo/fulltitle
         'lastuptime': '',  # mangainfo/recentupdatetime
         'lastuptimeex': '',  # mangainfo/recentupdatetime + ' 00:00:00'
         'links': [],  # From chapterinfo
         'logo': '',  # mangainfo/logopath
         'logos': '',  # mangainfo/logopath.split('-')[0]+'-s.jpg'
         'name': '',  # mangainfo/title
         'popular': 9999999, 'populars': '10000000+', 'rate': '20',
         'readmode': 50331648, 'readmode2': '0',
         'recomctrlparam': '101696', 'recomctrltype': '1',
         'recomdelay': '2000', 'recomenter': '', 'recomwords': '',
         'res': [],
         #'res': [{'cid': '0', #downloadview/cid
         #'csize': '4942', 'restype': '1'}]
         'resupno': '0', 'ret': 0, 'upno': '0'}
    lst = buka_lookup(
        'SELECT name, author, logo, finish, lastchap, lastuptime, lastup FROM comics WHERE mid = ?', (comicid,))[0]
    d['name'] = lst[0]
    d['author'] = lst[1]
    d['logo'] = lst[2]
    d['logos'] = lst[2]
    d['finish'] = str(lst[3])
    d['lastupcid'] = str(lst[4])
    d['lastuptime'] = time.strftime("%Y-%m-%d", time.gmtime(lst[5]))
    d['lastuptimeex'] = time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime(lst[5]))
    d['lastup'] = lst[6]
    chlst = buka_lookup(
        'SELECT cid, idx, title, type FROM chapters WHERE mid = ?', (comicid,))
    for lst in chlst:
        d['links'].append({'cid': str(lst[0]),  # chapterinfo/cid
                           'idx': str(lst[1] or lst[0]),  # chapterinfo/idx
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


def bukadown():
    func = flask.request.form.get('f') or flask.request.args.get('f')
    accepttw = flask.g.get('accepttw')
    L = (lambda x: zhconv(x, 'zh-tw')) if accepttw else (lambda x: x)
    template = 'buka_zhtw.html' if accepttw else 'buka.html'
    errmsg = flask.render_template(template, msg=flask.Markup(
        L('<p class="error">参数错误。<a href="javascript:history.back()">按此返回</a></p>')))
    if not func:
        return flask.render_template(template)
    elif func == 'i':
        cname = flask.request.args.get('name')
        if not cname:
            return flask.render_template(template, sname=cname)
        if cname.isdigit():
            rv = buka_lookup(
                "SELECT mid,name,author,lastchap,lastup,available FROM comics WHERE mid = ?", (cname,))
        else:
            rv = None
        mres = None
        sortfunc = lambda x: abs(len(cname) - len(x[1]))
        if rv:
            cinfo = rv[0]
        else:
            rv = buka_lookup(
                "SELECT mid,name,author,lastchap,lastup,available FROM comics WHERE name LIKE ?", ('%%%s%%' % zhconv(cname, 'zh-hans'),))
            if not rv:
                return flask.render_template(template, msg=flask.Markup(L('<p class="error">未找到符合的漫画。</p>')), sname=cname)
            rv = sorted(rv, key=sortfunc)
            cinfo = rv[0]
            if len(rv) > 1:
                mres = [('?f=i&name=%s' % r[0], r[1]) for r in rv]
        rv = buka_lookup(
            "SELECT cid,idx,title,type FROM chapters WHERE mid = ?", (cinfo[0],))
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
        rv = buka_lookup(
            "SELECT cid,idx,title,type FROM chapters WHERE mid = ?", (comicid,))
        chapname = dict((i[0], (buka_sortid(*i), buka_renamef(*i)))
                        for i in rv)
        chaps = sorted(map(int, filter(
            str.isdigit, flask.request.form.keys())), key=chapname.__getitem__, reverse=True)
        links = []
        for ch in chaps:
            rv = getbukaurl(comicid, ch)
            if rv:
                links.append((ch, chapname[ch][1], rv))
            else:
                links.append((ch, chapname[ch][1], ''))
        linklist = '\n'.join(i[2] for i in links)
        return flask.render_template(template, sname=comicid, links=links, linklist=linklist, coavail=bool(getchaporder(comicid)), mid=comicid)
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

TMPL403 = open(os.path.join(app.root_path, 'static/e403.html'), 'rb').read()
TMPL404 = open(os.path.join(app.root_path, 'static/e404.html'), 'rb').read()
TMPL500 = open(os.path.join(app.root_path, 'static/e500.html'), 'rb').read()


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
app.add_url_rule('/generate_204', 'generate_204', generate_204)
app.add_url_rule("/", 'index_glass', index_glass, subdomain='glass')
app.add_url_rule(
    "/<path:filename>", "file_glass", file_glass, subdomain='glass')
app.add_url_rule("/translate/", 'translate_alias', redirect_to="/wenyan/")
app.add_url_rule("/clozeword/", 'clozeword', clozeword)
app.add_url_rule("/name/", 'name_generator', name_generator)
app.add_url_rule("/uname/", 'uname_generator', username_generator)
app.add_url_rule("/buka/", 'bukadown', bukadown, methods=('GET', 'POST'))
app.add_url_rule(
    "/buka/bukadownloader.zip", 'bukadownloader_zip', bukadownloader_zip)
app.register_blueprint(bp_wenyan, subdomain='wenyan')
app.add_url_rule("/wenyan", 'wenyan_direct', redirect_wenyan_to_subdomain, methods=('GET', 'POST'))
app.add_url_rule("/wenyan/", 'redirect_wenyan_to_subdomain', redirect_wenyan_to_subdomain, methods=('GET', 'POST'))
app.add_url_rule("/wenyan/about", 'wenyan_about', wenyan_about)

if __name__ == "__main__":
    app.config['SERVER_NAME'] = None
    app.run(debug=True)
