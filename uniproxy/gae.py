#!/usr/bin/python
# -*- coding: utf-8 -*-
'''
@date: 2012-10-14
@author: shell.xu
'''
import copy, zlib, json, base64, random, logging, cStringIO
from urlparse import urlparse
from gevent import ssl, socket
from http import *
import hoh

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
        url = urlparse(baseurl)
        self.ssl = url.scheme == 'https'
        port = url.port or (443 if url.scheme.lower() == 'https' else 80)
        self.addr, self.path = (url.hostname, port), url.path
        self.algoname, self.key = algoname, key

    def client(self, query):
        req = request_http(self.path + '?' + query)
        sock = socket.socket()
        sock.connect(self.addr)
        if self.ssl: sock = ssl.wrap_socket(sock)
        stream = sock.makefile()
        req.sendto(stream)
        stream.flush()
        res = recv_msg(stream, HttpResponse)
        res.dbg_print()
        print res.read_body()

    def handler(self, req):
        if req.method.upper() == 'CONNECT': return None
        d = hoh.dumpreq(req)
        d = zlib.compress(d, 9)
        d = hoh.get_crypt(self.algoname, self.key)[0](d)
        d = base64.b64encode(d, '_%').strip('=')
        self.client(fakedict(d))
        print d

def main():
    import main
    main.initlog(logging.DEBUG)
    gae = GAE('http://localhost:8088/fakeurl', 'XOR', '1234567890')
    req = HttpRequest('GET', 'http://www.sina.com.cn', 'HTTP/1.1')
    req.stream = None
    gae.handler(req)

if __name__ == '__main__': main()
