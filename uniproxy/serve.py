#!/usr/bin/python
# -*- coding: utf-8 -*-
'''
@date: 2012-04-26
@author: shell.xu
'''
import time, base64, logging
import socks, proxy, conn, dnsserver, netfilter
from os import path
from urlparse import urlparse
from contextlib import contextmanager
from gevent import socket, dns, with_timeout, Timeout
from http import *

__all__ = ['ProxyServer',]

logger = logging.getLogger('server')

def mgr_default(self, req):
    req.read_body()
    return response_http(404, body='Page not found')

def fmt_reqinfo(info):
    req, usesocks, addr, t = info
    return '%s %s %s' % (
        req.method, req.uri.split('?', 1)[0], 'socks' if usesocks else 'direct')

def ssh_to_proxy(cfg, max_conn=None):
    if 'sockport' in cfg:
        return {'type': 'socks5', 'addr': '127.0.0.1', 'port': cfg['sockport'],
                'max_conn': max_conn, 'name': 'socks5:%s@%s' % (cfg['username'], cfg['sshhost'])}
    elif 'listenport' in cfg:
        return {'type': 'http', 'addr': '127.0.0.1', 'port': cfg['listenport'][0],
                'max_conn': max_conn, 'name': 'http:%s@%s' % (cfg['username'], cfg['sshhost'])}
    raise Exception('unknown ssh define')

class ProxyServer(object):
    proxytypemap = {'socks5': socks.SocksManager, 'http': conn.HttpManager}
    srv_urls = {}

    def __init__(self, config):
        logger.info('init ProxyServer')
        self.config = config
        self.connpool, self.worklist = [], []
        self.proxy_auth = proxy.get_proxy_auth(self.config.get('users'))
        self.dns = dnsserver.DNSServer(
            dnsserver=self.config.get('dnsserver', None),
            cachesize=self.config.get('dnscache', 512),
            timeout=self.config.get('dnstimeout', 30))
        self.reload()
        self.direct = conn.DirectManager(self.dns)

    def reload(self):
        proxies = self.config.get('proxies', None)
        if proxies is None: proxies = []
        if self.config.get('max_conn', None):
            proxies.extend([ssh_to_proxy(cfg, self.config['max_conn'])
                            for cfg in self.config['sshs']])
        self.connpool = [self.proxytypemap[proxy['type']](**proxy) for proxy in proxies]
        self.upstream = self.config.get('upstream')

        self.dns.empty()
        self.dns.loadlist(self.config.get('dnsfake'))
        self.whitenf = self.load_filter(netfilter.NetFilter, 'whitenets')
        self.blacknf = self.load_filter(netfilter.NetFilter, 'blacknets')

    def load_filter(self, cls, name):
        if not self.config.get(name): return None
        f = cls()
        for filepath in self.config[name]: f.loadfile(filepath)
        return f

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

    def get_conn_mgr(self, direct):
        if direct: return self.direct
        return min(self.connpool, key=lambda x: x.size())

    def usesocks(self, hostname, req):
        if self.whitenf or self.blacknf:
            addr = self.dns.gethostbyname(hostname)
            if req: req.address = addr
            if addr is None: return False
            logger.debug('hostname: %s, addr: %s' % (hostname, addr))
            if self.whitenf is not None and addr in self.whitenf:
                return True
            if self.blacknf is not None and addr not in self.blacknf:
                return True
        return False

    def do_req(self, req, addr):
        authres = self.proxy_auth(req)
        if authres is not None:
            authres.sendto(req.stream)
            return authres
        reqconn = req.method.upper() == 'CONNECT'

        req.url = urlparse(req.uri)
        if not reqconn and not req.url.netloc:
            logger.info('manager %s' % (req.url.path,))
            res = self.srv_urls.get(req.url.path, mgr_default)(self, req)
            res.sendto(req.stream)
            return res

        if reqconn:
            hostname, func, tout = (
                req.uri, proxy.connect, self.config.get('conn_tout'))
        else:
            hostname, func, tout = (
                req.url.netloc, proxy.http, self.config.get('http_tout'))
        usesocks = self.usesocks(hostname.split(':', 1)[0], req)
        reqinfo = (req, usesocks, addr, time.time())

        # if usesocks and self.upstream:
        if self.upstream:
            with self.with_worklist(reqinfo):
                logger.info(fmt_reqinfo(reqinfo))
                res = self.upstream.handler(req)
                if res is not None:
                    res.sendto(req.stream)
                    req.stream.flush()
                    return res

        with self.with_worklist(reqinfo):
            logger.info(fmt_reqinfo(reqinfo))
            if not tout:
                return func(req, self.get_conn_mgr(not usesocks))
            try:
                return with_timeout(
                    tout, func, req, self.get_conn_mgr(not usesocks))
            except Timeout, err:
                logger.warn('connection timeout: %s' % req.uri)

    def http_handler(self, sock, addr):
        stream = sock.makefile()
        try:
            while self.do_req(recv_msg(stream, HttpRequest), addr): pass
        except (EOFError, socket.error): logger.debug('network error')
        except Exception, err: logger.exception('unknown')
        sock.close()

    def final(self): logger.info('system exit')
