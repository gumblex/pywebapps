#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import flask
from config import *
from werkzeug.contrib.fixers import ProxyFix

app = flask.Flask(__name__)
app.wsgi_app = ProxyFix(app.wsgi_app, num_proxies=2)
app.secret_key = SECRETKEY

from wenyan import bp_wenyan

app.register_blueprint(bp_wenyan)

if __name__ == "__main__":
    app.config['SERVER_NAME'] = None
    app.run(port=5002, debug=True)
