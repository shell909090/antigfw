#!/usr/bin/python
# -*- coding: utf-8 -*-
'''
@date: 2012-10-14
@author: shell.xu
'''
import zlib, copy, json, base64, logging
from urlparse import urlparse
from http import *
from hoh import *
from config import *

from gevent.pywsgi import WSGIServer
from gevent import socket

def application(env, start_response):
    if env['REQUEST_METHOD'] == 'GET': d = env['QUERY_STRING']
    elif env['REQUEST_METHOD'] == 'POST': d = env['wsgi.input'].read()
    else:
        start_response('404 Not Found')
        return

    d = base64.b64decode(d.replace('&', '').replace('=', '') + '==', '_%')
    d = get_crypt(config['method'], config['key'])[1](d)
    req, options = loadmsg(zlib.decompress(d), HttpRequest)

    reqx = copy.copy(req)
    req.url = urlparse(req.uri)
    reqx.uri = '%s?%s' % (req.url.path, req.url.query) if req.url.query else req.url.path
    res = http_client(
        reqx,
        (req.url.netloc, req.url.port or (443 if req.url.scheme == 'https' else 80)),
        socket.socket)
    
    start_response('200 OK', [('Content-Type', 'application/mp4')])
    d = zlib.compress(dumpres(res), 9)
    yield get_crypt(config['method'], config['key'])[0](d)

def initlog(lv, logfile=None):
    rootlog = logging.getLogger()
    if logfile: handler = logging.FileHandler(logfile)
    else: handler = logging.StreamHandler()
    handler.setFormatter(
        logging.Formatter(
            '%(asctime)s,%(msecs)03d %(name)s[%(levelname)s]: %(message)s',
            '%H:%M:%S'))
    rootlog.addHandler(handler)
    rootlog.setLevel(lv)

if __name__ == '__main__':
    initlog(logging.DEBUG)
    WSGIServer(('', 8088), application).serve_forever()
