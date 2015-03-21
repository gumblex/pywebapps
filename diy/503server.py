#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import http.server
from socketserver import ThreadingMixIn

HTMLFILE = open(os.path.join(os.environ['OPENSHIFT_REPO_DIR'], 'diy/templates/e503.html'), 'rb').read()
HTMLLEN = str(len(HTMLFILE))

class ThreadingHTTPServer(ThreadingMixIn, http.server.HTTPServer):
	pass

class HTTPHandler(http.server.BaseHTTPRequestHandler):
	def do_HEAD(self):
		self.send_response(503)
		self.send_header('Retry-After', '300')
		self.end_headers()
		return

	def do_GET(self):
		self.send_response(503)
		self.send_header('Retry-After', '300')
		self.send_header('Content-Length', HTMLLEN)
		self.send_header('Content-Type', 'text/html')
		self.end_headers()
		self.wfile.write(HTMLFILE)
		return

	do_POST = do_GET

def run(server_class=ThreadingHTTPServer,
		handler_class=HTTPHandler):
	server_address = (os.environ['OPENSHIFT_DIY_IP'], int(os.environ['OPENSHIFT_DIY_PORT']))
	httpd = server_class(server_address, handler_class)
	httpd.serve_forever()

if __name__ == '__main__':
	run()
