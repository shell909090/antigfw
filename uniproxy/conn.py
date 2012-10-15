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

class DirectManager(object):
    name = 'direct'

    def __init__(self, dns): self.count, self.dns = 0, dns

    def size(self): return 65536
    def stat(self): return '%d/unlimited' % self.count

    @contextmanager
    def socket(self):
        self.count += 1
        logger.debug('%s %s allocated' % (self.name, self.stat()))
        sock = socket.socket()
        connect = sock.connect
        def newconn(addr):
            # 没办法，gevent的dns这时如果碰到多ip返回值，会直接报错
            try: connect(addr)
            except dns.DNSError:
                address = self.dns.gethostbyname(addr[0])
                if address is None: raise Exception('DNS not found')
                sock.connect((address, addr[1]))
        sock.connect = newconn
        try: yield sock
        finally:
            sock.close()
            logger.debug('%s %s released' % (self.name, self.stat()))
            self.count -= 1

class Manager(object):
    def __init__(self, max_conn=10, name=None, **kargs):
        self.smph, self.max_conn = coros.BoundedSemaphore(max_conn), max_conn
        self.name, self.creator = name, socket.socket

    def size(self): return self.max_conn - self.smph.counter
    def stat(self): return '%d/%d' % (self.size(), self.max_conn)

    @contextmanager
    def socket(self):
        with self.smph:
            logger.debug('%s %s allocated' % (self.name, self.stat()))
            sock = self.creator()
            try: yield sock
            finally:
                sock.close()
                logger.debug('%s %s released' % (self.name, self.stat()))

def http_connect(sock, target, username=None, password=None):
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

def http_proxy(proxyaddr, username=None, password=None):
    def reciver(func):
        def creator(family=socket.AF_INET, type=socket.SOCK_STREAM, proto=0):
            sock = func(family, type, proto)
            sock.connect(proxyaddr)
            def newconn(addr): http_connect(sock, addr, username, password)
            sock.connect, sock.connect_ex = newconn, newconn
            return sock
        return creator
    return reciver

class HttpManager(Manager):
    def __init__(self, addr, port, username=None, password=None,
                 max_conn=10, name=None, **kargs):
        super(HttpManager, self).__init__(max_conn, name or 'http:%s:%s' % (addr, port))
        self.creator = http_proxy((addr, port), username, password)(self.creator)
