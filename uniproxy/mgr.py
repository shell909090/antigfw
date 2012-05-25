#!/usr/bin/python
# -*- coding: utf-8 -*-
'''
@date: 2012-05-25
@author: shell.xu
'''
import logging, cStringIO
import serve
from http import *

logger = logging.getLogger('manager')

@serve.ProxyServer.register('/')
def mgr_socks_stat(ps, req, stream):
    namemap = {}
    if not ps.config.get('socks', None):
        namemap = dict(('127.0.0.1:%s' % srv['proxyport'],
                        '%s@%s' % (srv['username'], srv['sshhost']))
                       for srv in ps.config['servers'])
    def fmt_rcd(s):
        n, r = s.stat()
        return '%s	%s' % (namemap.get(n, n), r)
    body = ['socks stat',] + [fmt_rcd(s) for s in ps.sockcfg] + \
        ['', 'avtive conntions',] + ps.worklist
    req.recv_body(stream)
    response_http(stream, 200, body='\r\n'.join(body))

@serve.ProxyServer.register('/reload')
def mgr_reload(ps, req, stream):
    ps.init()
    req.recv_body(stream)
    response_http(stream, 302, headers=[('location', '/')])

@serve.ProxyServer.register('/quit')
def mgr_quit(req, stream): sys.exit(-1)

@serve.ProxyServer.register('/domain')
def mgr_domain_list(ps, req, stream):
    domain_template='''<html><body><form action="/add" method="POST"><input name="domain"/><input type="submit" name="submit"/></form><pre>%s</pre></body></html>'''
    strs = cStringIO.StringIO()
    ps.filter.save(strs)
    req.recv_body(stream)
    response_http(stream, 200, body=domain_template % strs.getvalue())

@serve.ProxyServer.register('/add')
def mgr_domain_add(ps, req, stream):
    strs = cStringIO.StringIO()
    req.recv_body(stream, strs.write)
    form = dict([i.split('=', 1) for i in strs.getvalue().split('&')])
    if form.get('domain', '') and form['domain'] not in ps.filter:
        try:
            with open(ps.config['filter'][0], 'a') as fo:
                fo.write(form['domain'] + '\n')
        except: pass
        ps.filter.add(form['domain'])
    response_http(stream, 302, headers=[('location', '/domain')])
