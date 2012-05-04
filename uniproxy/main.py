#!/usr/bin/python
# -*- coding: utf-8 -*-
'''
@date: 2012-04-26
@author: shell.xu
'''
import sys, logging, gevent
import socks, proxy, dofilter
from http import *
from os import path
from urlparse import urlparse
from contextlib import contextmanager
from gevent import socket, server

def import_config(*cfgs):
    d = {}
    for cfg in reversed(cfgs):
        try:
            with open(path.expanduser(cfg)) as fi:
                eval(compile(fi.read(), cfg, 'exec'), d)
        except (OSError, IOError): pass
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

def make_worklist():
    worklist = []
    @contextmanager
    def with_worklist(desc):
        worklist.append(desc)
        try: yield
        finally: worklist.remove(desc)
    return with_worklist, worklist

def proxy_server():
    sockcfg = []
    config = {}
    filter = dofilter.DomainFilter()
    with_worklist, worklist = make_worklist()

    def init(*cfgs):
        if cfgs: config.update(import_config(*cfgs))
        initlog(getattr(logging, config.get('loglevel', 'WARNING')),
                config.get('logfile', None))

        socks_srv = config.get('socks', None)
        max_conn = config.get('max_conn', None)
        if socks_srv is None and max_conn:
            socks_srv = [('127.0.0.1', int(srv['proxyport']), max_conn)
                         for srv in config['servers']]
        del sockcfg[:]
        for host, port, max_conn in socks_srv:
            sockcfg.append(socks.SocksManager(host, port, max_conn=max_conn))

        filter.empty()
        for filepath in config['filter']: filter.loadfile(filepath)
        filter.loadfile('gfw')
        return config.get('localip', ''), config.get('localport', 8118)

    def get_socks_factory():
        return min(sockcfg, key=lambda x: x.size()).with_socks

    def mgr_default(req, stream):
        response_http(req, stream, 404, body='Page not found')

    def mgr_reload(req, stream):
        init()
        response_http(req, stream, 200, body='done')

    def mgr_quit(req, stream): sys.exit(-1)

    def mgr_socks_stat(req, stream):
        namemap = {}
        if not config.get('socks', None):
            namemap = dict(('127.0.0.1:%s' % srv['proxyport'],
                            '%s@%s' % (srv['username'], srv['sshhost']))
                           for srv in config['servers'])
        def fmt_rcd(s):
            n, r = s.stat()
            return '%s	%s' % (namemap.get(n, n), r)
        body = ['socks stat',] + [fmt_rcd(s) for s in sockcfg] + \
            ['', 'avtive conntions',] + worklist
        response_http(req, stream, 200, body='\r\n'.join(body))

    srv_urls = {'/reload': mgr_reload, '/kill': mgr_quit,
                '/stat': mgr_socks_stat}

    def do_req(req, stream):
        u = urlparse(req.uri)
        if req.method.upper() == 'CONNECT':
            hostname, func = u.path, proxy.connect
        else:
            if not u.netloc:
                logger.info('manager %s' % (u.path,))
                return srv_urls.get(u.path, mgr_default)(req, stream)
            hostname, func = u.netloc, proxy.http
        usesocks = hostname.split(':', 1)[0] in filter
        logger.info('%s %s %s' % (
                req.method, req.uri.split('?', 1)[0],
                'socks' if usesocks else 'direct'))
        with with_worklist('%s %s' % (req.method, req.uri.split('?', 1)[0])):
            return func(req, stream,
                        get_socks_factory() if usesocks else with_sock)

    def handler(sock, addr):
        stream = sock.makefile()
        try:
            while do_req(recv_headers(stream), stream): pass
        except (EOFError, socket.error): pass
        except Exception, err: logger.exception('unknown')
        sock.close()

    def final(): logger.info('system exit')

    return init, handler, final

def main(*cfgs):
    init, handler, final = proxy_server()
    try:
        try: server.StreamServer(init(*cfgs), handler).serve_forever()
        except KeyboardInterrupt: pass
    finally: final()

if __name__ == '__main__': main(*sys.argv[1:])
