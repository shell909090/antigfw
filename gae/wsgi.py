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

from gevent.pywsgi import WSGIServer
from gevent import socket

config = {
    'method': 'XOR', 'key': '1234567890'
    }

def application(env, start_response):
    # print env['REQUEST_METHOD'], env['PATH_INFO'],
    if env['REQUEST_METHOD'] != 'GET':
        # print env['wsgi.input'].read()
        start_response('404 Not Found')
        return

    d = env['QUERY_STRING'].replace('&', '').replace('=', '')
    d = base64.b64decode(d + '==', '_%')
    d = get_crypt(config['method'], config['key'])[1](d)
    req, options = loadmsg(zlib.decompress(d), HttpRequest)

    reqx = copy.copy(req)
    req.url = urlparse(req.uri)
    reqx.uri = '%s?%s' % (req.url.path, req.url.query) if req.url.query else req.url.path
    res = http_client(
        reqx,
        (req.url.netloc, req.url.port or (443 if req.url.scheme == 'https' else 80)),
        socket.socket)
    
    start_response('200 OK', [('Content-Type', 'text')])
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
