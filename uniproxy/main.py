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

def main(*cfgs):
    if not cfgs:
        print 'no configure'
        return
    config = import_config(*cfgs)
    initlog(getattr(logging, config.get('loglevel', 'WARNING')),
            config.get('logfile', None))
    addr = (config.get('localip', ''), config.get('localport', 8118))
    ps = serve.ProxyServer(config)
    try:
        if config.get('dnsproxy'):
            gevent.spawn(ps.dns.server, config.get('dnsport', 53))
        try: server.StreamServer(addr, ps.http_handler).serve_forever()
        except KeyboardInterrupt: pass
    finally: ps.final()

if __name__ == '__main__': main(*sys.argv[1:])
