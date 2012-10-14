#!/usr/bin/python
# -*- coding: utf-8 -*-
'''
@date: 2012-09-29
@author: shell.xu
'''
import logging
from contextlib import contextmanager
from gevent import socket, coros, dns
from http import *

logger = logging.getLogger('conn')

class Manager(object):
    def __init__(self, max_conn=10, name=None, **kargs):
        self.smph, self.max_conn = coros.BoundedSemaphore(max_conn), max_conn
        self.name = name

    def size(self): return self.max_conn - self.smph.counter
    def stat(self): return '%d/%d' % (self.size(), self.max_conn)

class DirectManager(object):
    name = 'direct'

    def __init__(self, dns): self.count, self.dns = 0, dns

    def size(self): return 65536
    def stat(self): return '%d/unlimited' % self.count

    @contextmanager
    def get_socket(self, addr, port):
        self.count += 1
        sock = socket.socket()
        try:
            # 没办法，gevent的dns这时如果碰到多ip返回值，会直接报错
            try: sock.connect((addr, port))
            except dns.DNSError:
                # 这下不会拖慢响应了，要死最多死这个上下文
                addr = self.dns.gethostbyname(addr)
                if addr is None: raise Exception('DNS not found')
                sock.connect((addr, port))
            yield sock
        finally:
            sock.close()
            self.count -= 1

def http_proxy(proxy, target, username=None, password=None):
    sock = socket.socket()
    sock.connect(proxy)
    stream = sock.makefile()

    req = HttpRequest('CONNECT', '%s:%d' % target, 'HTTP/1.1')
    if username and password:
        req.add_header('Proxy-Authorization',
                       base64.b64encode('Basic %s:%s' % (username, password)))
    req.send_header(stream)

    res = recv_msg(stream, HttpResponse)
    if res.code == 200: return sock
    sock.close()
    return None

class HttpManager(Manager):
    def __init__(self, addr, port, username=None, password=None,
                 max_conn=10, name=None, **kargs):
        super(HttpManager, self).__init__(max_conn, name or 'http:%s:%s' % (addr, port))
        self.s = ((addr, port), username, password)

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
