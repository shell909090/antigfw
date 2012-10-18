#!/usr/bin/python
# -*- coding: utf-8 -*-
'''
@date: 2012-05-25
@author: shell.xu
'''
import sys, logging, gevent, serve, mgr
from os import path
from gevent import server

logger = logging.getLogger('main')

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

def main(*cfgs):
    if not cfgs:
        print 'no configure'
        return
    ps = serve.ProxyServer(cfgs)
    initlog(getattr(logging, ps.config.get('loglevel', 'WARNING')),
            ps.config.get('logfile', None))
    logger.info('ProxyServer inited')
    addr = (ps.config.get('localip', ''), ps.config.get('localport', 8118))
    try:
        if ps.config.get('dnsport'):
            gevent.spawn(ps.dns.server, ps.config.get('dnsport'))
        try: server.StreamServer(addr, ps.http_handler).serve_forever()
        except KeyboardInterrupt: pass
    finally: ps.final()

if __name__ == '__main__': main(*sys.argv[1:])
