#!/usr/bin/python
# -*- coding: utf-8 -*-
'''
@date: 2012-10-14
@author: shell.xu
'''
import copy, zlib, json, base64, random, cStringIO, proxy

headerlist = ['Accept', 'Accept-Charset', 'Accept-Encoding', 'Accept-Language', 'Accept-Ranges', 'Age', 'Allow', 'Authorization', 'Cache-Control', 'Connection', 'Content-Encoding', 'Content-Language', 'Content-Length', 'Content-Location', 'Content-Md5', 'Content-Range', 'Content-Type', 'Date', 'Etag', 'Expect', 'Expires', 'From', 'Host', 'If-Match', 'If-Modified-Since', 'If-None-Match', 'If-Range', 'If-Unmodified-Since', 'Last-Modified', 'Location', 'Max-Forwards', 'Pragma', 'Proxy-Authenticate', 'Proxy-Authorization', 'Range', 'Referer', 'Retry-After', 'Server', 'Te', 'Trailer', 'Transfer-Encodin', 'Upgrade', 'User-Agent', 'Vary', 'Via', 'Warning', 'Www-Authenticate', 'Cookie']
headernum = dict(zip(headerlist, xrange(len(headerlist))))

def dumpreq(req, **options):
    headers = [(h, v) for h, v in req.headers if not h.startswith('Proxy')]
    headers = map(lambda i: (headernum.get(i[0], i[0]), i[1]), headers)
    buf = cStringIO.StringIO()
    req.recv_body(req.stream, buf)
    return json.dumps((req.method, req.uri, req.version,
                       headers, buf.getvalue(), options))

def fakedict(s):
    kl, vl = 10, 150
    r = []
    while s:
        s, k, v = s[kl+vl:], s[:kl], s[kl:kl+vl]
        r.append((k, v))
    return '&'.join(['%s=%s' % i for i in r])

def do_aes(key, s):
    from Crypto.Cipher import AES
    from Crypto import Random
    iv = Random.new().read(AES.block_size)
    cipher = AES.new(key, AES.MODE_CFB, iv)
    return iv + cipher.encrypt(s)

def msg_encoder(d, key):
    d = zlib.compress(d, 9)
    d = do_aes(key, d)
    d = base64.b64encode(d, '_%').strip('=')
    d = fakedict(d)
    return d

def application(req):
    d = dumpreq(req)
    print d
    d = msg_encoder(d, '1234567890123456')
    raise EOFError()
