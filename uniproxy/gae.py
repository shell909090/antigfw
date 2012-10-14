#!/usr/bin/python
# -*- coding: utf-8 -*-
'''
@date: 2012-10-14
@author: shell.xu
'''
import copy, zlib, json, base64, random, cStringIO
from http import *

headerlist = ['Accept', 'Accept-Charset', 'Accept-Encoding', 'Accept-Language', 'Accept-Ranges', 'Age', 'Allow', 'Authorization', 'Cache-Control', 'Connection', 'Content-Encoding', 'Content-Language', 'Content-Length', 'Content-Location', 'Content-Md5', 'Content-Range', 'Content-Type', 'Date', 'Etag', 'Expect', 'Expires', 'From', 'Host', 'If-Match', 'If-Modified-Since', 'If-None-Match', 'If-Range', 'If-Unmodified-Since', 'Last-Modified', 'Location', 'Max-Forwards', 'Pragma', 'Proxy-Authenticate', 'Proxy-Authorization', 'Range', 'Referer', 'Retry-After', 'Server', 'Te', 'Trailer', 'Transfer-Encodin', 'Upgrade', 'User-Agent', 'Vary', 'Via', 'Warning', 'Www-Authenticate', 'Cookie']
headernum = dict(zip(headerlist, xrange(len(headerlist))))

def dumpreq(req, **options):
    headers = [(h, v) for h, v in req.headers if not h.startswith('Proxy')]
    headers = map(lambda i: (headernum.get(i[0], i[0]), i[1]), headers)
    buf = cStringIO.StringIO()
    req.recv_body(req.stream, buf)
    return json.dumps((req.method, req.uri, req.version,
                       headers, buf.getvalue(), options))

def loadreq(s):
    r = json.loads(s)
    req = HttpRequest(*r[:3])
    req.headers, req.data = r[3], r[4]
    return req, r[5]

def fakedict(s):
    r = []
    while s:
        kl, vl = random.randint(5, 15), random.randint(50, 200)
        s, k, v = s[kl+vl:], s[:kl], s[kl:kl+vl]
        r.append((k, v))
    return '&'.join(['%s=%s' % i for i in r])

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

def msg_encoder(d, method, key):
    d = zlib.compress(d, 9)
    d = get_crypt(method, key)[0](d)
    d = base64.b64encode(d, '_%').strip('=')
    return d

def msg_decoder(d, method, key):
    d = base64.b64decode(d + '==', '_%')
    d = get_crypt(method, key)[1](d)
    return zlib.decompress(d)

class GAE(object):
    def __init__(self, baseurl):
        self.baseurl = baseurl

    def handler(self, req):
        if req.method.upper() == 'CONNECT': return None
        d = msg_encoder(dumpreq(req), 'XOR', '1234567890123456')
        if len(d) < 500:
            d = fakedict(d)
        print d
        raise EOFError()
