#!/usr/bin/python
# -*- coding: utf-8 -*-
'''
@date: 2012-10-14
@author: shell.xu
'''
from config import *
from hoh import *
import copy, logging

from gevent.pywsgi import WSGIServer
from gevent import socket

def http_over_http(d):
    d = base64.b64decode(d.replace('&', '').replace('=', '') + '==', '_%')
    d = get_crypt(config['method'], config['key'])[1](d)
    req, options = loadmsg(zlib.decompress(d), HttpRequest)

    reqx = copy.copy(req)
    url = urlparse(req.uri)
    reqx.uri = url.path + ('?'+url.query if url.query else '')
    res = http_client(
        reqx,
        (url.netloc, url.port or (443 if url.scheme == 'https' else 80)),
        socket.socket)
    d = zlib.compress(dumpres(res), 9)
    return get_crypt(config['method'], config['key'])[0](d)

def redirget(uri):
    url = urlparse(uri)
    req = HttpRequest('GET', url.path + ('?'+url.query if url.query else ''),
                      'HTTP/1.1')
    req.set_header('Host', url.netloc)
    res = http_client(
        req, (url.netloc, url.port or (443 if url.scheme == 'https' else 80)),
        socket.socket)
    return res

def application(env, start_response):
    if env['PATH_INFO'] == config['fakeurl']:
        if env['REQUEST_METHOD'] == 'GET': d = env['QUERY_STRING']
        elif env['REQUEST_METHOD'] == 'POST': d = env['wsgi.input'].read()
        else:
            start_response('404 Not Found')
            return
        d = http_over_http(d)
        start_response('200 OK', [('Content-Type', 'application/mp4')])
        yield d
    elif env['PATH_INFO'] == config['geturl']:
        res = redirget(base64.b64decode(env['QUERY_STRING']))
        start_response('%s %s' % (res.code, res.phrase), res.headers)
        for d in res.read_chunk(res.stream): yield d

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
    WSGIServer(('0.0.0.0', 8088), application).serve_forever()
