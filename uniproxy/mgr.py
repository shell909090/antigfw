#!/usr/bin/python
# -*- coding: utf-8 -*-
'''
@date: 2012-05-25
@author: shell.xu
'''
import logging
import main

logger = logging.getLogger('manager')

@main.ProxyServer.register('/')
def mgr_socks_stat(ps, req, stream):
    namemap = {}
    if not ps.config.get('socks', None):
        namemap = dict(('127.0.0.1:%s' % srv['proxyport'],
                        '%s@%s' % (srv['username'], srv['sshhost']))
                       for srv in ps.config['servers'])
    def fmt_rcd(s):
        n, r = s.stat()
        return '%s	%s' % (namemap.get(n, n), r)
    body = ['socks stat',] + [fmt_rcd(s) for s in sockcfg] + \
        ['', 'avtive conntions',] + worklist
    req.recv_body(stream)
    response_http(stream, 200, body='\r\n'.join(body))

@main.ProxyServer.register('/reload')
def mgr_reload(ps, req, stream):
    ps.init()
    req.recv_body(stream)
    response_http(stream, 302, headers=[('location', '/')])

@main.ProxyServer.register('/quit')
def mgr_quit(req, stream): sys.exit(-1)

@main.ProxyServer.register('/domain')
def mgr_domain_list(ps, req, stream):
    domain_template='''<html><body><form action="/add" method="POST"><input name="domain"/><input type="submit" name="submit"/></form><pre>%s</pre></body></html>'''
    strs = StringIO.StringIO()
    ps.filter.save(strs)
    req.recv_body(stream)
    response_http(stream, 200, body=domain_template % strs.getvalue())

@main.ProxyServer.register('/add')
def mgr_domain_add(ps, req, stream):
    strs = StringIO.StringIO()
    req.recv_body(stream, strs.write)
    form = dict([i.split('=', 1) for i in strs.getvalue().split('&')])
    if form.get('domain', '') and form['domain'] not in filter:
        try:
            with open(ps.config['filter'][0], 'a') as fo:
                fo.write(form['domain'] + '\n')
        except: pass
        filter.add(form['domain'])
    response_http(stream, 302, headers=[('location', '/domain')])
