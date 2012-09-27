#!/usr/bin/python
# -*- coding: utf-8 -*-
'''
@date: 2012-04-27
@author: shell.xu
'''
import os, copy, time, logging
from urlparse import urlparse
from contextlib import contextmanager
from gevent import socket, select, coros
from http import *

__all__ = ['connect', 'http']

logger = logging.getLogger('proxy')
VERBOSE = False

def http_connect(proxy, target, username=None, password=None):
    sock = socket.socket()
    sock.connect(proxy)
    stream = sock.makefile()

    req = HttpRequest('CONNECT', '%s:%d' % target, 'HTTP/1.1')
    if username and password:
        req.add_header('proxy-authorization',
                       base64.b64encode('Basic %s:%s' % (username, password)))
    req.send_header(stream)

    res = recv_msg(stream, HttpResponse)
    if res.code == 200: return sock
    sock.close()
    return None

class HttpManager(object):
    def __init__(self, addr, port, username=None, password=None,
                 max_conn=10, name=None, **kargs):
        self.s = ((addr, port), username, password)
        self.smph, self.max_conn = coros.Semaphore(max_conn), max_conn
        self.name = name or 'http:%s:%s' % (addr, port)

    def size(self): return self.max_conn - self.smph.counter
    def stat(self): return '%d/%d' % (self.size(), self.max_conn)

    @contextmanager
    def get_socket(self, addr, port):
        with self.smph:
            logger.debug('http:%s:%d %d/%d allocated.' % (
                    self.s[0][0], self.s[0][1], self.size(), self.max_conn))
            sock = http_proxy(self.s[0], (addr, port), self.s[1], self.s[2])
            try: yield sock
            finally: 
                if sock: sock.close()
                logger.debug('http:%s:%d %d/%d, released.' % (
                        self.s[0][0], self.s[0][1], self.size(), self.max_conn))

def get_proxy_auth(users):
    def all_pass(req): return None
    def proxy_auth(req):
        auth = req.get_header('proxy-authorization')
        if auth:
            req.headers = [(k, v) for k, v in req.headers if k != 'proxy-authorization']
            username, password = base64.b64decode(auth[6:]).split(':')
            if users.get(username, None) == password: return None
        logging.info('proxy authenticate failed')
        return response_http(407, headers=[('Proxy-Authenticate', 'Basic realm="users"')])
    return proxy_auth if users else all_pass

def parse_target(uri):
    u = urlparse(uri)
    r = (u.netloc or u.path).split(':', 1)
    if len(r) > 1: port = int(r[1])
    else: port = 443 if u.scheme.lower() == 'https' else 80
    return r[0], port, '%s?%s' % (u.path, u.query) if u.query else u.path

def connect(req, sock_factory):
    hostname, port, uri = parse_target(req.uri)
    try:
        with sock_factory.get_socket(hostname, port) as sock:
            res = HttpResponse(req.version, 200, 'OK')
            res.send_header(req.stream)
            req.stream.flush()

            fd1, fd2 = req.stream.fileno(), sock.fileno()
            rlist = [fd1, fd2]
            while True:
                for rfd in select.select(rlist, [], [])[0]:
                    try: d = os.read(rfd, BUFSIZE)
                    except OSError: d = ''
                    if not d: raise EOFError()
                    try: os.write(fd2 if rfd == fd1 else fd1, d)
                    except OSError: raise EOFError()
    finally: logger.info('%s closed' % req.uri)

def http(req, sock_factory):
    t = time.time()
    hostname, port, uri = parse_target(req.uri)
    reqx = copy.copy(req)
    reqx.uri = uri
    reqx.headers = [(h, v) for h, v in req.headers if not h.startswith('proxy')]
    with sock_factory.get_socket(hostname, port) as sock:
        stream1 = sock.makefile()

        if VERBOSE: req.dbg_print()
        reqx.send_header(stream1)
        reqx.recv_body(req.stream, stream1.write, raw=True)
        stream1.flush()

        res = recv_msg(stream1, HttpResponse)
        if VERBOSE: res.dbg_print()
        res.send_header(req.stream)
        hasbody = req.method.upper() != 'HEAD' and res.code not in CODE_NOBODY
        res.recv_body(stream1, req.stream.write, hasbody, raw=True)
        req.stream.flush()
    res.connection = req.get_header('proxy-connection', '').lower() == 'keep-alive'
    logger.debug('%s with %d in %0.2f, %s' % (
            req.uri.split('?', 1)[0], res.code, time.time() - t,
            req.get_header('proxy-connection', 'closed').lower()))
    return res
