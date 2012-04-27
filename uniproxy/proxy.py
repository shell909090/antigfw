#!/usr/bin/python
# -*- coding: utf-8 -*-
'''
@date: 2012-04-27
@author: shell.xu
'''
import os, logging
from urlparse import urlparse
from gevent import select
from http import *

__all__ = ['recv_headers', 'connect', 'http']

logger = logging.getLogger('proxy')
VERBOSE = False

def parse_target(uri):
    u = urlparse(uri)
    r = (u.netloc or u.path).split(':', 1)
    if len(r) > 1: port = int(r[1])
    else: port = 443 if u.scheme.lower() == 'https' else 80
    return r[0], port, '%s?%s' % (u.path, u.query)

def connect(req, stream, sock_factory):
    hostname, port, uri = parse_target(req.uri)
    with sock_factory(hostname, port) as sock:
        res = HttpResponse(req.version, 200, DEFAULT_PAGES[200][0])
        res.sendto(stream)
        stream.flush()

        rlist = [stream.fileno(), sock.fileno()]
        while True:
            for rfd in select.select(rlist, [], [])[0]:
                d = os.read(rfd, BUFSIZE)
                if not d: raise EOFError()
                if rfd == stream.fileno():
                    os.write(sock.fileno(), d)
                else: os.write(stream.fileno(), d)

def http(req, stream, sock_factory):
    hostname, port, uri = parse_target(req.uri)
    headers = [(h, v) for h, v in req.headers if not h.startswith('proxy')]
    with sock_factory(hostname, port) as sock:
        stream1 = sock.makefile()

        if VERBOSE: req.dbg_print()
        stream1.write(' '.join((req.method, uri, req.version)))
        send_headers(stream1, headers)
        req.recv_body(stream, stream1.write, raw=True)
        stream1.flush()

        res = recv_headers(stream1, HttpResponse)
        if VERBOSE: res.dbg_print()
        res.sendto(stream)
        hasbody = req.method.upper() != 'HEAD' and res.code not in CODE_NOBODY
        res.recv_body(stream1, stream.write, hasbody, raw=True)
        stream.flush()
    return req.get_header('proxy-connection', '').lower() == 'keep-alive'
