#!/usr/bin/python
# -*- coding: utf-8 -*-
'''
@date: 2012-05-25
@author: shell.xu
'''
import base64, logging, cStringIO
import serve, template
from http import *

logger = logging.getLogger('manager')

def auth_manager(func):
    def realfunc(ps, req):
        managers = ps.config['managers']
        if not managers: return func(ps, req)
        auth = req.get_header('authorization')
        if auth:
            username, password = base64.b64decode(auth[6:]).split(':')
            if managers.get(username, None) == password: return func(ps, req)
        logging.info('access to %s without auth' % req.uri.split('?', 1)[0])
        return response_http(401, headers=[('WWW-Authenticate', 'Basic realm="managers"')])
    return realfunc

socks_stat = template.Template(template='''
<html><body>
<table>
  <tr>
    <td><a href="/reload">reload</a></td><td><a href="/quit">quit</a></td>
    <td><a href="/domain">domain</a></td>
    {%if ps.whitenf:%}<td><a href="/whitenets">whitenets</a></td>{%end%}
    {%if ps.blacknf:%}<td><a href="/blacknets">blacknets</a></td>{%end%}
  </tr>
  <tr><td>dns cache</td><td>dns connections</td></tr>
  <tr><td>{%=len(ps.dns.cache)%}/{%=ps.dns.cachesize%}</td><td>{%=ps.dns.stat()%}</td></tr>
</table><p/>
<table>
  <tr><td>socks</td><td>stat</td></tr>
  <tr><td>{%=ps.direct.name%}</td><td>{%=ps.direct.stat()%}</td></tr>
  {%for i in ps.connpool:%}
    <tr><td>{%=i.name%}</td><td>{%=i.stat()%}</td></tr>
  {%end%}
</table><p/>
active connections
<table>
  <tr><td>source</td><td>method</td><td>url</td><td>type</td></tr>
  {%for req, usesocks, addr in ps.worklist:%}
    <tr><td>{%=addr[0]%}:{%=addr[1]%}</td><td>{%=req.method%}</td>
    <td>{%=req.uri.split('?', 1)[0]%}</td><td>{%='socks' if usesocks else 'direct'%}</td></tr>
  {%end%}
</table></body></html>
''')

@serve.ProxyServer.register('/')
@auth_manager
def mgr_socks_stat(ps, req):
    req.recv_body(req.stream)
    return response_http(200, body=socks_stat.render({'ps': ps}))

@serve.ProxyServer.register('/reload')
@auth_manager
def mgr_reload(ps, req):
    ps.reload()
    req.recv_body(req.stream)
    return response_http(302, headers=[('location', '/')])

@serve.ProxyServer.register('/quit')
@auth_manager
def mgr_quit(req, stream): sys.exit(-1)

domain_list = template.Template(template='''
<html><body>
<form action="/add" method="POST">
  <input name="domain"/>
  <input type="submit" name="submit"/>
</form>
{%import cStringIO%}
{%strs = cStringIO.StringIO()
ps.filter.save(strs)%}
<pre>{%=strs.getvalue()%}</pre>
</body></html>
''')

@serve.ProxyServer.register('/domain')
@auth_manager
def mgr_domain_list(ps, req):
    req.recv_body(req.stream)
    return response_http(200, body=domain_list.render({'ps': ps}))

@serve.ProxyServer.register('/add')
@auth_manager
def mgr_domain_add(ps, req):
    strs = cStringIO.StringIO()
    req.recv_body(req.stream, strs.write)
    form = dict([i.split('=', 1) for i in strs.getvalue().split('&')])
    if form.get('domain', '') and form['domain'] not in ps.filter:
        try:
            with open(ps.config['filter'][0], 'a') as fo:
                fo.write(form['domain'] + '\n')
        except: pass
        ps.filter.add(form['domain'])
    return response_http(302, headers=[('location', '/domain')])

filter_list = template.Template(template='''
<html><body>
{%import cStringIO%}
{%strs = cStringIO.StringIO()
filter.save(strs)%}
<pre>{%=strs.getvalue()%}</pre>
</body></html>
''')

@serve.ProxyServer.register('/whitenets')
@auth_manager
def mgr_netfilter_list(ps, req):
    req.recv_body(req.stream)
    return response_http(200, body=filter_list.render({'filter': ps.whitenf}))

@serve.ProxyServer.register('/blacknets')
@auth_manager
def mgr_netfilter_list(ps, req):
    req.recv_body(req.stream)
    return response_http(200, body=filter_list.render({'filter': ps.blacknf}))
