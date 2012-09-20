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
    body = '''<html><body>
<table><tr><td>socks</td><td>stat</td></tr>%s</table><p/>
active connections<table><tr><td>source</td><td>method</td><td>url</td>
<td>type</td></tr>%s</table></body></html>''' % (
        ''.join(['''<tr><td>%s</td><td>%s</td></tr>''' % (s.name, s.stat())
                 for s in ps.sockcfg]),
        ''.join(('''<tr><td>%s:%d</td><td>%s</td><td>%s</td><td>%s</td></tr>''' % (
                addr[0], addr[1], req.method, req.uri.split('?', 1)[0],
                'socks' if usesocks else 'direct')
                 for req, usesocks, addr in ps.worklist)))
    req.recv_body(stream)
    response_http(stream, 200, body=body)

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
