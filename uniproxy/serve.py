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

def mgr_default(self, req):
    req.recv_body(req.stream)
    return response_http(404, body='Page not found')

def fmt_reqinfo(info):
    req, usesocks, addr = info
    return '%s:%d %s %s %s' % (
        addr[0], addr[1], req.method, req.uri.split('?', 1)[0],
        'socks' if usesocks else 'direct')

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
                if addr is None: return
                sock.connect((addr, port))
            yield sock
        finally:
            sock.close()
            self.count -= 1

class ProxyServer(object):
    proxytypemap = {'socks5': socks.SocksManager}
    srv_urls = {}

    def __init__(self, *cfgs):
        self.cfgs, self.config = cfgs, {}
        self.connpool, self.worklist = [], []
        self.filter = dofilter.DomainFilter()
        self.direct, self.dns = None, None
        self.whitenf, self.blacknf = None, None

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
        self.connpool = [self.proxytypemap[proxy['type']](**proxy) for proxy in proxies]

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
        self.dns = netfilter.DNSServer(self.get_conn_mgr,
                                       dnsserver=self.config.get('dnsserver', None),
                                       cachesize=self.config.get('dnscache', 1000))
        self.direct = DirectManager(self.dns)

        self.load_filters()
        self.whitenf = self.load_netfilter('whitenets')
        self.blacknf = self.load_netfilter('blacknets')
        return self.config.get('localip', ''), self.config.get('localport', 8118)

    def get_conn_mgr(self, direct):
        if direct: return self.direct
        return min(self.connpool, key=lambda x: x.size())

    def proxy_auth(self, req):
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

    def do_req(self, req, addr):
        u = urlparse(req.uri)
        if req.method.upper() == 'CONNECT':
            hostname, func = u.path, proxy.connect
        else:
            if not u.netloc:
                logger.info('manager %s' % (u.path,))
                res = self.srv_urls.get(u.path, mgr_default)(self, req)
                res.sendto(req.stream)
                return res
            hostname, func = u.netloc, proxy.http
        if not self.proxy_auth(req):
            res = response_http(407, headers=[('Proxy-Authenticate',
                                               'Basic realm="users"')])
            res.sendto(req.stream)
            return res
        usesocks = self.usesocks(hostname.split(':', 1)[0])
        reqinfo = (req, usesocks, addr)
        with self.with_worklist(reqinfo):
            logger.info(fmt_reqinfo(reqinfo))
            return func(req, self.get_conn_mgr(not usesocks))

    def handler(self, sock, addr):
        stream = sock.makefile()
        try:
            while self.do_req(recv_msg(stream, HttpRequest), addr): pass
        except (EOFError, socket.error): logger.debug('network error')
        except Exception, err: logger.exception('unknown')
        sock.close()

    def final(self): logger.info('system exit')
