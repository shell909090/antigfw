#!/usr/bin/python
# -*- coding: utf-8 -*-
'''
@date: 2012-10-15
@author: shell.xu
'''
import json, zlib, base64, random, logging
from urlparse import urlparse
from http import *

headerlist = ['Accept', 'Accept-Charset', 'Accept-Encoding', 'Accept-Language', 'Accept-Ranges', 'Age', 'Allow', 'Authorization', 'Cache-Control', 'Connection', 'Content-Encoding', 'Content-Language', 'Content-Length', 'Content-Location', 'Content-Md5', 'Content-Range', 'Content-Type', 'Date', 'Etag', 'Expect', 'Expires', 'From', 'Host', 'If-Match', 'If-Modified-Since', 'If-None-Match', 'If-Range', 'If-Unmodified-Since', 'Last-Modified', 'Location', 'Max-Forwards', 'Pragma', 'Proxy-Authenticate', 'Proxy-Authorization', 'Range', 'Referer', 'Retry-After', 'Server', 'Te', 'Trailer', 'Transfer-Encodin', 'Upgrade', 'User-Agent', 'Vary', 'Via', 'Warning', 'Www-Authenticate', 'Cookie']
headernum = dict(zip(headerlist, xrange(len(headerlist))))
headername = dict(zip(xrange(len(headerlist)), headerlist))

def packdata(h, d):
    h = json.dumps(h)
    l = len(h)
    if l > 0xffff: raise Exception('header too long')
    return chr(l>>8)+chr(l&0xff) + h + d

def unpackdata(s):
    l = (ord(s[0])<<8) + ord(s[1])
    return json.loads(s[2:2+l]), s[2+l:]

def dumpreq(req, **options):
    headers = [(h, v) for h, v in req.headers if not h.startswith('Proxy')]
    headers = map(lambda i: (headernum.get(i[0], i[0]), i[1]), headers)
    return packdata((req.method, req.uri, req.version, headers, options), req.read_body())

def dumpres(res, **options):
    headers = map(lambda i: (headernum.get(i[0], i[0]), i[1]), res.headers)
    return packdata((res.version, res.code, res.phrase, headers, options), res.read_body())

def loadmsg(s, cls):
    r, d = unpackdata(s)
    req = cls(*r[:3])
    req.headers, req.body = map(lambda i: (headername.get(i[0], i[0]), i[1]), r[3]), d
    return req, r[4]

def get_crypt(algoname, key):
    algo = getattr(__import__('Crypto.Cipher', fromlist=[algoname,]), algoname)
    if algo is None: raise Exception('unknown cipher %s' % algoname)
    if algoname in ['AES', 'Blowfish', 'DES3']:
        def block_encrypt(s):
            from Crypto import Random
            iv = Random.new().read(algo.block_size)
            cipher = algo.new(key, algo.MODE_CFB, iv)
            return iv + cipher.encrypt(s)
        def block_decrypt(s):
            iv = s[:algo.block_size]
            cipher = algo.new(key, algo.MODE_CFB, iv)
            return cipher.decrypt(s[algo.block_size:])
        return block_encrypt, block_decrypt
    elif algoname in ['ARC4', 'XOR']:
        cipher = algo.new(key)
        return cipher.encrypt, cipher.decrypt
    else: raise Exception('unknown cipher %s' % name)

def fakedict(s):
    r = []
    while s:
        kl, vl = random.randint(5, 15), random.randint(50, 200)
        s, k, v = s[kl+vl:], s[:kl], s[kl:kl+vl]
        r.append((k, v))
    return '&'.join(['%s=%s' % i for i in r])

class HttpOverHttp(object):
    MAXGETSIZE = 512
    logger = logging.getLogger('hoh')
    name = 'hoh'

    def __init__(self, baseurl, algoname, key):
        from gevent import socket
        self.baseurl, self.url = baseurl, urlparse(baseurl)
        self.socket = socket.socket
        if self.url.scheme == 'https': self.socket = ssl_socket()(self.socket)
        port = self.url.port or (443 if self.url.scheme.lower() == 'https' else 80)
        self.addr, self.path = (self.url.hostname, port), self.url.path
        self.algoname, self.key = algoname, key

    def client(self, query):
        if len(query) >= self.MAXGETSIZE:
            logger.debug('query in post mode.')
            req = request_http(self.path, data=query)
            req.set_header('Context-Length', str(len(query)))
            req.set_header('Context-Type', 'multipart/form-data')
        else:
            logger.debug('query in get mode.')
            req = request_http(self.path + '?' + query)
        req.set_header('Host', self.url.hostname)
        req.debug()
        res = http_client(req, self.addr, self.socket)
        res.debug()
        if res.code != 200: return
        return res.read_body()

    def handler(self, req):
        if req.method.upper() == 'CONNECT': return None
        d = zlib.compress(dumpreq(req), 9)
        d = get_crypt(self.algoname, self.key)[0](d)
        d = base64.b64encode(d, '_%').strip('=')
        d = self.client(fakedict(d))
        # if d is None: return None
        d = get_crypt(self.algoname, self.key)[1](d)
        res, options = loadmsg(zlib.decompress(d), HttpResponse)
        return res

class GAE(HttpOverHttp):
    name = 'gae'
    ipaddr = '74.125.128.106'
    def __init__(self, gaeid, algoname, key, ssl=False):
        super(GAE, self).__init__('%s://%s.appspot.com/fakeurl' % (
                'https' if ssl else 'http', gaeid), algoname, key)
        self.addr = (self.ipaddr, self.addr[1])
