#!/usr/bin/python
# -*- coding: utf-8 -*-
'''
@date: 2012-04-26
@author: shell.xu
'''
import sys, logging, gevent, StringIO
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

def proxy_server(cfgs):
    sockcfg = []
    config = {}
    filter = dofilter.DomainFilter()
    worklist = []

    @contextmanager
    def with_worklist(desc):
        logger.info(desc)
        worklist.append(desc)
        try: yield
        finally: worklist.remove(desc)

    def init():
        config.update(import_config(*cfgs))
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
        return config.get('localip', ''), config.get('localport', 8118)

    def get_socks_factory():
        return min(sockcfg, key=lambda x: x.size()).with_socks

    def mgr_default(req, stream):
        req.recv_body(stream)
        response_http(stream, 404, body='Page not found')

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
        req.recv_body(stream)
        response_http(stream, 200, body='\r\n'.join(body))

    def mgr_reload(req, stream):
        init()
        req.recv_body(stream)
        response_http(stream, 302, headers=[('location', '/')])

    def mgr_quit(req, stream): sys.exit(-1)

    domain_template='''<html><body><form action="/add" method="POST"><input name="domain"/><input type="submit" name="submit"/></form><pre>%s</pre></body></html>'''
    def mgr_domain_list(req, stream):
        strs = StringIO.StringIO()
        filter.save(strs)
        req.recv_body(stream)
        response_http(stream, 200, body=domain_template % strs.getvalue())

    def mgr_domain_update(req, stream):
        strs = StringIO.StringIO()
        req.recv_body(stream, strs.write)
        form = dict([i.split('=', 1) for i in strs.getvalue().split('&')])
        if form.get('domain', '') and form['domain'] not in filter:
            try:
                with open(config['filter'][0], 'a') as fo:
                    fo.write(form['domain'] + '\n')
            except: pass
            filter.add(form['domain'])
        response_http(stream, 302, headers=[('location', '/domain')])

    srv_urls = {'/': mgr_socks_stat, '/reload': mgr_reload,
                '/quit': mgr_quit, '/domain': mgr_domain_list,
                '/add': mgr_domain_update, '/save': mgr_doamin_save}

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
        with with_worklist('%s %s %s' % (req.method, req.uri.split('?', 1)[0],
                                         'socks' if usesocks else 'direct')):
            return func(req, stream,
                        get_socks_factory() if usesocks else with_sock)

    def handler(sock, addr):
        stream = sock.makefile()
        try:
            while do_req(recv_msg(stream, HttpRequest), stream): pass
        except (EOFError, socket.error): pass
        except Exception, err: logger.exception('unknown')
        sock.close()

    def final(): logger.info('system exit')

    return init, handler, final

def main(*cfgs):
    if not cfgs: return
    init, handler, final = proxy_server(cfgs)
    try:
        try: server.StreamServer(init(), handler).serve_forever()
        except KeyboardInterrupt: pass
    finally: final()

if __name__ == '__main__': main(*sys.argv[1:])
