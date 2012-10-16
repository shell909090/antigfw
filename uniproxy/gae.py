#!/usr/bin/python
# -*- coding: utf-8 -*-
'''
@date: 2012-10-14
@author: shell.xu
'''
import copy, zlib, json, base64, random, logging, cStringIO
from urlparse import urlparse
from gevent import ssl, socket
import conn
from http import *
from hoh import *

logger = logging.getLogger('gae')

def fakedict(s):
    r = []
    while s:
        kl, vl = random.randint(5, 15), random.randint(50, 200)
        s, k, v = s[kl+vl:], s[:kl], s[kl:kl+vl]
        r.append((k, v))
    return '&'.join(['%s=%s' % i for i in r])

def msg_decoder(d, method, key):
    d = base64.b64decode(d + '==', '_%')
    d = get_crypt(method, key)[1](d)
    return zlib.decompress(d)

class GAE(object):
    def __init__(self, baseurl, algoname, key):
        self.baseurl, url = baseurl, urlparse(baseurl)
        self.socket = socket.socket
        if url.scheme == 'https': self.socket = ssl_socket()(self.socket)
        port = url.port or (443 if url.scheme.lower() == 'https' else 80)
        self.addr, self.path = (url.hostname, port), url.path
        self.algoname, self.key = algoname, key

    def fmt_reqinfo(self, req):
        return '%s %s %s' % (req.method, req.uri.split('?', 1)[0], 'gae')

    def client(self, query):
        req = request_http(self.path + '?' + query)
        res = http_client(req, self.addr, self.socket)
        return res.read_body()

    def handler(self, req):
        if req.method.upper() == 'CONNECT': return None
        logger.info(self.fmt_reqinfo(req))
        d = zlib.compress(dumpreq(req), 9)
        d = get_crypt(self.algoname, self.key)[0](d)
        d = base64.b64encode(d, '_%').strip('=')
        d = self.client(fakedict(d))
        d = get_crypt(self.algoname, self.key)[1](d)
        res, options = loadmsg(zlib.decompress(d), HttpResponse)
        return res

def main():
    import main
    main.initlog(logging.DEBUG)
    gae = GAE('http://localhost:8088/fakeurl', 'XOR', '1234567890')
    req = HttpRequest('GET', 'http://www.sina.com.cn/', 'HTTP/1.1')
    req.set_header('Host', 'www.sina.com.cn')
    req.stream = None
    gae.handler(req)

if __name__ == '__main__': main()
