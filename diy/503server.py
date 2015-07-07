#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import time
import http.server
from socketserver import ThreadingMixIn


class Unbuffered(object):

    def __init__(self, stream):
        self.stream = stream

    def write(self, data):
        self.stream.write(data)
        self.stream.flush()

    def __getattr__(self, attr):
        return getattr(self.stream, attr)

#sys.stdout = Unbuffered(sys.stdout)
#sys.stderr = Unbuffered(sys.stderr)

HTMLFILE = open(os.path.join(
    os.environ['OPENSHIFT_REPO_DIR'], 'diy/templates/e503.html'), 'rb').read()
HTMLLEN = str(len(HTMLFILE))


class ThreadingHTTPServer(ThreadingMixIn, http.server.HTTPServer):
    pass


class HTTPHandler(http.server.BaseHTTPRequestHandler):

    def send_response(self, code, message=None):
        self.send_response_only(code, message)
        self.send_header('Server', self.version_string())
        self.send_header('Date', self.date_time_string())

    def log_message(self, format, *args):
        sys.stderr.write('%s - - [%s] %s "%s" "%s"\n' % (
            self.headers.get('X-Forwarded-For', self.address_string()),
            self.log_date_time_string(), format % args, self.headers.get('Referer', '-'), self.headers.get('User-Agent', '-')))
        sys.stderr.flush()

    def log_date_time_string(self):
        """Return the current time formatted for logging."""
        lt = time.localtime(time.time())
        s = time.strftime('%d/%%3s/%Y:%H:%M:%S %z', lt) % self.monthname[lt[1]]
        return s

    def do_HEAD(self):
        self.send_response(503)
        self.log_request(503)
        self.send_header('Retry-After', '300')
        self.end_headers()
        return

    def do_GET(self):
        self.send_response(503)
        self.log_request(503, HTMLLEN)
        self.send_header('Retry-After', '300')
        self.send_header('Content-Length', HTMLLEN)
        self.send_header('Content-Type', 'text/html')
        self.end_headers()
        self.wfile.write(HTMLFILE)
        return

    do_POST = do_GET


def run(server_class=ThreadingHTTPServer,
        handler_class=HTTPHandler):
    server_address = (
        os.environ['OPENSHIFT_DIY_IP'], int(os.environ['OPENSHIFT_DIY_PORT']))
    httpd = server_class(server_address, handler_class)
    httpd.serve_forever()

if __name__ == '__main__':
    run()
