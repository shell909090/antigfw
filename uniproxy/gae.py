#!/usr/bin/python
# -*- coding: utf-8 -*-
'''
@date: 2012-10-14
@author: shell.xu
'''
import copy, zlib, json, base64, random, cStringIO
from http import *
import hoh

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
        self.baseurl, self.algoname, self.key = baseurl, algoname, key

    def client(self, query):
        req = request_http(self.baseurl + '?' + query)
        req.sendto()

    def handler(self, req):
        if req.method.upper() == 'CONNECT': return None
        d = hoh.dumpreq(req)
        d = zlib.compress(d, 9)
        d = hoh.get_crypt(self.algoname, self.key)[0](d)
        d = base64.b64encode(d, '_%').strip('=')
        d = fakedict(d)
        print d

def main():
    gae = GAE('http://localhost:8088/fakeurl', 'XOR', '1234567890')
    req = HttpRequest('GET', 'http://www.sina.com.cn', 'HTTP/1.1')
    req.stream = None
    gae.handler(req)

if __name__ == '__main__': main()
