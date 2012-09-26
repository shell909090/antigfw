#!/usr/bin/python
# -*- coding: utf-8 -*-
'''
@date: 2012-04-26
@author: shell.xu
'''
import base64, logging
import socket as orsocket
import socks, proxy, dofilter, netfilter
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

def mgr_default(self, req, stream):
    req.recv_body(stream)
    response_http(stream, 404, body='Page not found')

class ProxyServer(object):
    proxytypemap = {'socks5': socks.SocksManager}
    srv_urls = {}

    def __init__(self, *cfgs):
        self.cfgs, self.config = cfgs, {}
        self.sockcfg, self.worklist = [], []
        self.filter = dofilter.DomainFilter()
        self.dns, self.whitenf, self.blacknf = None, None, None

    @classmethod
    def register(cls, url):
        def inner(func):
            cls.srv_urls[url] = func
            return func
        return inner

    @contextmanager
    def with_worklist(self, reqinfo):
        self.worklist.append(reqinfo)
        try: yield
        finally: self.worklist.remove(reqinfo)

    @contextmanager
    def with_sock(self, addr, port):
        sock = socket.socket()
        # 没办法，gevent的dns这时如果碰到多ip返回值，会直接报错
        try: sock.connect((addr, port))
        except dns.DNSError:
            # 这下不会拖慢响应了，要死最多死这个上下文
            addr = self.dns.gethostbyname(addr)
            if addr is None: return
            sock.connect((addr, port))
        try: yield sock
        finally: sock.close()

    @staticmethod
    def fmt_reqinfo(info):
        req, usesocks, addr = info
        return '%s:%d %s %s %s' % (
            addr[0], addr[1], req.method, req.uri.split('?', 1)[0],
            'socks' if usesocks else 'direct')

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

    def load_netfilter(self, name):
        if not self.config.get(name): return None
        nf = netfilter.NetFilter()
        for filepath in self.config[name]: nf.loadfile(filepath)
        return nf

    def init(self):
        self.config.update(import_config(*self.cfgs))
        initlog(getattr(logging, self.config.get('loglevel', 'WARNING')),
                self.config.get('logfile', None))
        logger.info('init ProxyServer')

        self.load_socks()
        self.load_filters()
        self.dns = netfilter.DNSServer(self.get_socks_factory(),
                                       dnsserver=self.config.get('dnsserver', None),
                                       cachesize=self.config.get('dnscache', 1000))
        self.whitenf = self.load_netfilter('whitenets')
        self.blacknf = self.load_netfilter('blacknets')
        return self.config.get('localip', ''), self.config.get('localport', 8118)

    def get_socks_factory(self):
        return min(self.sockcfg, key=lambda x: x.size())

    def proxy_auth(self, req, stream):
        users = self.config.get('users')
        if not users: return True
        auth = req.get_header('proxy-authorization')
        if auth:
            req.headers = [(k, v) for k, v in req.headers if k != 'proxy-authorization']
            username, password = base64.b64decode(auth[6:]).split(':')
            if users.get(username, None) == password:
                return True
        logging.info('proxy authenticate failed')
        return False

    def usesocks(self, hostname):
        if hostname in self.filter: return True
        if self.whitenf or self.blacknf:
            addr = self.dns.gethostbyname(hostname)
            if addr is None: return False
            logger.debug('hostname: %s, addr: %s' % (hostname, addr))
            if self.whitenf and addr in self.whitenf: return True
            if self.blacknf and addr not in self.blacknf: return True
        return False

    def do_req(self, req, stream, addr):
        u = urlparse(req.uri)
        if req.method.upper() == 'CONNECT':
            hostname, func = u.path, proxy.connect
        else:
            if not u.netloc:
                logger.info('manager %s' % (u.path,))
                return self.srv_urls.get(u.path, mgr_default)(self, req, stream)
            hostname, func = u.netloc, proxy.http
        if not self.proxy_auth(req, stream):
            response_http(stream, 407, headers=[('Proxy-Authenticate', 'Basic realm="users"')])
        usesocks = self.usesocks(hostname.split(':', 1)[0])
        reqinfo = (req, usesocks, addr)
        with self.with_worklist(reqinfo):
            logger.info(self.fmt_reqinfo(reqinfo))
            sf = self.get_socks_factory().with_socks if usesocks else self.with_sock
            return func(req, stream, sf)

    def handler(self, sock, addr):
        stream = sock.makefile()
        try:
            while self.do_req(recv_msg(stream, HttpRequest), stream, addr): pass
        except (EOFError, socket.error): logger.debug('network error')
        except Exception, err: logger.exception('unknown')
        sock.close()

    def final(self): logger.info('system exit')
