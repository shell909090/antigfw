#!/usr/bin/python
# -*- coding: utf-8 -*-
'''
@date: 2012-10-17
@author: shell.xu
'''
import sys
sys.path.append('../uniproxy/')
from config import *
from hoh import *

from google.appengine.api import urlfetch

def dump_gaeres(res, **options):
    headers = map(lambda i: (headernum.get(i[0], i[0]), i[1]), res.headers)
    return packdata(('HTTP/1.1', res.status_code, DEFAULT_PAGES[res.status_code][0],
                     headers, options), res.content)

def http_over_http(d):
    d = base64.b64decode(d.replace('&', '').replace('=', '') + '==', '_%')
    d = get_crypt(config['method'], config['key'])[1](d)
    req, options = loadmsg(zlib.decompress(d), HttpRequest)

    res = urlfetch.fetch(req.uri, req.body, req.method, dict(req.headers), deadline=30)
    d = zlib.compress(dump_gaeres(res), 9)
    return get_crypt(config['method'], config['key'])[0](d)

def application(env, start_response):
    if env['PATH_INFO'] == config['fakeurl']:
        if env['REQUEST_METHOD'] == 'GET': d = env['QUERY_STRING']
        elif env['REQUEST_METHOD'] == 'POST':
            d = env['wsgi.input'].read(int(env['HTTP_CONTEXT_LENGTH']))
        else:
            start_response('404 Not Found', [])
            return
        d = http_over_http(d)
        start_response('200 OK', [('Content-Type', 'application/mp4')])
        yield d
    elif env['PATH_INFO'] == config['geturl']:
        res = urlfetch.fetch(base64.b64decode(env['QUERY_STRING']))
        start_response('%s %s' % (res.status_code, DEFAULT_PAGES[res.status_code][0]),
                       res.headers.items())
        yield res.content
