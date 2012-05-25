#!/usr/bin/python
# -*- coding: utf-8 -*-
'''
@date: 2012-05-25
@author: shell.xu
'''
import sys, serve, mgr
from gevent import server

def main(*cfgs):
    if not cfgs: return
    ps = serve.ProxyServer(*cfgs)
    try:
        try: server.StreamServer(ps.init(), ps.handler).serve_forever()
        except KeyboardInterrupt: pass
    finally: ps.final()

if __name__ == '__main__': main(*sys.argv[1:])
