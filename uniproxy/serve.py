#!/usr/bin/python
# -*- coding: utf-8 -*-
'''
@date: 2012-04-26
@author: shell.xu
'''
import logging
import socks, proxy, dofilter
from http import *
from os import path
from urlparse import urlparse
from contextlib import contextmanager
from gevent import socket

__all__ = ['ProxyServer',]

def import_config(*cfgs):
    d = {}
    for cfg in reversed(cfgs):
        try:
            with open(path.expanduser(cfg)) as fi:
                eval(compile(fi.read(), cfg, 'exec'), d)
        except (OSError, IOError): logger.error('import config')
    return dict([(k, v) for k, v in d.iteritems() if not k.startswith('_')])

def initlog(lv, logfile=None):
    rootlog = logging.getLogger()
    if logfile: handler = logging.FileHandler(logfile)
    else: handler = logging.StreamHandler()
    handler.setFormatter(
        logging.Formatter(
            '%(asctime)s,%(msecs)03d %(name)s[%(levelname)s]: %(message)s',
            '%H:%M:%S'))
    rootlog.addHandler(handler)
    rootlog.setLevel(lv)

logger = logging.getLogger('server')

@contextmanager
def with_sock(addr, port):
    sock = socket.socket()
    sock.connect((addr, port))
    try: yield sock
    finally: sock.close()

def mgr_default(self, req, stream):
    req.recv_body(stream)
    response_http(stream, 404, body='Page not found')

class ProxyServer(object):
    proxytypemap = {'http': socks.SocksManager}
    srv_urls = {}

    def __init__(self, *cfgs):
        self.cfgs = cfgs
        self.sockcfg = []
        self.config = {}
        self.filter = dofilter.DomainFilter()
        self.worklist = []

    @classmethod
    def register(cls, url):
        def inner(func):
            cls.srv_urls[url] = func
            return func
        return inner

    @contextmanager
    def with_worklist(self, desc):
        self.worklist.append(desc)
        try: yield
        finally: self.worklist.remove(desc)

    def load_socks(self):
        socks_srv = self.config.get('socks', None)
        max_conn = self.config.get('max_conn', None)
        if not socks_srv and max_conn:
            socks_srv = [('http', '127.0.0.1', int(srv['proxyport']), max_conn)
                         for srv in self.config['servers']]
        del self.sockcfg[:]
        for proxytype, host, port, max_conn in socks_srv:
            self.sockcfg.append(self.proxytypemap[proxytype](
                    host, port, max_conn=max_conn))

    def load_filters(self):
        self.filter.empty()
        for filepath in self.config['filter']: self.filter.loadfile(filepath)

    def init(self):
        self.config.update(import_config(*self.cfgs))
        initlog(getattr(logging, self.config.get('loglevel', 'WARNING')),
                self.config.get('logfile', None))
        logger.info('init ProxyServer')

        self.load_socks()
        self.load_filters()
        return self.config.get('localip', ''), self.config.get('localport', 8118)

    def get_socks_factory(self):
        return min(self.sockcfg, key=lambda x: x.size()).with_socks

    def do_req(self, req, stream):
        u = urlparse(req.uri)
        if req.method.upper() == 'CONNECT':
            hostname, func = u.path, proxy.connect
        else:
            if not u.netloc:
                logger.info('manager %s' % (u.path,))
                return self.srv_urls.get(u.path, mgr_default)(self, req, stream)
            hostname, func = u.netloc, proxy.http
        usesocks = hostname.split(':', 1)[0] in self.filter
        reqid = '%s %s %s' % (req.method, req.uri.split('?', 1)[0],
                              'socks' if usesocks else 'direct')
        with self.with_worklist(reqid):
            logger.info(reqid)
            return func(req, stream,
                        self.get_socks_factory() if usesocks else with_sock)

    def handler(self, sock, addr):
        stream = sock.makefile()
        try:
            while self.do_req(recv_msg(stream, HttpRequest), stream): pass
        except (EOFError, socket.error): pass
        except Exception, err: logger.exception('unknown')
        sock.close()

    def final(self): logger.info('system exit')
