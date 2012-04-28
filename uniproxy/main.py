#!/usr/bin/python
# -*- coding: utf-8 -*-
'''
@date: 2012-04-26
@author: shell.xu
'''
import sys, logging, gevent
import utils, socks, http, proxy, dofilter
from urlparse import urlparse
from contextlib import contextmanager
from gevent import socket, dns, server

utils.initlog(logging.INFO)
logger = logging.getLogger('server')

@contextmanager
def with_sock(addr, port):
    sock = socket.socket()
    sock.connect((addr, port))
    try: yield sock
    finally: sock.close()

def proxy_server(cfgs):
    sockcfg = []
    def get_socks_factory():
        s = sockcfg[0]
        return s.with_socks

    cfg = utils.import_config(*cfgs)
    for host, port, max_conn in cfg.get('socks', [('127.0.0.1', 7777, 30),]):
        sockcfg.append(socks.SocksManager(host, port, max_conn=max_conn))
    filter = dofilter.DomainFilter()
    for filepath in cfg.get('filter', ['gfw',]): filter.loadfile(filepath)

    def do_req(req, stream):
        u = urlparse(req.uri)
        usesocks = (u.netloc or u.path).split(':', 1)[0] in filter
        logger.info('%s %s %s' % (
                req.method, req.uri, 'socks' if usesocks else 'direct'))
        func = proxy.connect if req.method.upper() == 'CONNECT' else proxy.http
        sock_factory = get_socks_factory() if usesocks else with_sock
        r = func(req, stream, sock_factory)
        return r

    def sock_handler(sock, addr):
        stream = sock.makefile()
        try:
            while do_req(proxy.recv_headers(stream), stream): pass
        except EOFError: pass
        except Exception, err: logger.exception('unknown')
        sock.close()

    serv = server.StreamServer(
        (cfg.get('localip', ''), cfg.get('localport', 8118)),
        sock_handler)
    serv.serve_forever()

def main():
    proxy_server(sys.argv[1:])

if __name__ == '__main__': main()
