#!/usr/bin/python
# -*- coding: utf-8 -*-
'''
@date: 2012-04-26
@author: shell.xu
'''
import logging
import socket as orsocket
import socks, proxy, dofilter
from http import *
from os import path
from urlparse import urlparse
from contextlib import contextmanager
from gevent import socket, dns

__all__ = ['ProxyServer',]

def import_config(*cfgs):
    d = {}
    for cfg in reversed(cfgs):
        if not path.exists(cfg): continue
        try:
            with open(path.expanduser(cfg)) as fi:
                eval(compile(fi.read(), cfg, 'exec'), d)
            logger.info('import config %s' % cfg)
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
    # 没办法，gevent的dns这时如果碰到多ip返回值，会直接报错
    try: sock.connect((addr, port))
    except dns.DNSError:
        # 在这里再用普通方式获得一下ip就OK了，不过会略略拖慢一下响应速度
        addr = orsocket.gethostbyname(addr)
        sock.connect((addr, port))
    try: yield sock
    finally: sock.close()

def mgr_default(self, req, stream):
    req.recv_body(stream)
    response_http(stream, 404, body='Page not found')

class ProxyServer(object):
    proxytypemap = {'socks5': socks.SocksManager}
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

    def ssh_to_proxy(self, cfg):
        if 'sockport' in cfg:
            return {
                'type': 'socks5', 'addr': '127.0.0.1', 'port': cfg['sockport'],
                'max_conn': self.config.get('max_conn', None),
                'name': 'socks5:%s@%s' % (cfg['username'], cfg['sshhost'])}
        elif 'listenport' in cfg:
            return {
                'type': 'http', 'addr': '127.0.0.1', 'port': cfg['listenport'][0],
                'max_conn': self.config.get('max_conn', None),
                'name': 'http:%s@%s' % (cfg['username'], cfg['sshhost'])}

    def load_socks(self):
        proxies = self.config.get('proxies', None)
        if not proxies and self.config.get('max_conn', None):
            proxies = [self.ssh_to_proxy(cfg) for cfg in self.config['sshs']]
        self.sockcfg = [self.proxytypemap[proxy['type']](**proxy) for proxy in proxies]

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
        except (EOFError, socket.error): logger.info('network error')
        except Exception, err: logger.exception('unknown')
        sock.close()

    def final(self): logger.info('system exit')
