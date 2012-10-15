#!/usr/bin/python
# -*- coding: utf-8 -*-
'''
@date: 2012-10-14
@author: shell.xu
'''
import zlib, json, base64
import hoh

config = {
    'method': 'XOR', 'key': '1234567890'
    }

def application(env, start_response):
    print env['REQUEST_METHOD'], env['PATH_INFO'],
    if env['REQUEST_METHOD'] != 'GET':
        # print env['wsgi.input'].read()
        start_response('404 Not Found')
        return
    d = env['QUERY_STRING'].replace('&', '').replace('=', '')
    d = base64.b64decode(d + '==', '_%')
    d = hoh.get_crypt(config['method'], config['key'])[1](d)
    d = zlib.decompress(d)
    req = hoh.loadreq(d)
    print req.method, req.uri, req.version
    print req.headers
    start_response('200 OK', [('Content-Type', 'text')])
    yield ''

if __name__ == '__main__':
    from gevent.pywsgi import WSGIServer
    WSGIServer(('', 8088), application).serve_forever()
