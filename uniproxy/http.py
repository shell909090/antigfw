#!/usr/bin/python
# -*- coding: utf-8 -*-
'''
@date: 2012-04-26
@author: shell.xu
'''
import os, logging
from urlparse import urlparse
from gevent import socket, select

__all__ = ['recv', 'connect', 'http_proxy']
logger = logging.getLogger('http')

VERBOSE = False
BUFSIZE = 512
CODE_NOBODY = [100, 101, 204, 304]
DEFAULT_PAGES = {
    100:('Continue', 'Request received, please continue'),
    101:('Switching Protocols',
          'Switching to new protocol; obey Upgrade header'),

    200:('OK', ''),
    201:('Created', 'Document created, URL follows'),
    202:('Accepted', 'Request accepted, processing continues off-line'),
    203:('Non-Authoritative Information', 'Request fulfilled from cache'),
    204:('No Content', 'Request fulfilled, nothing follows'),
    205:('Reset Content', 'Clear input form for further input.'),
    206:('Partial Content', 'Partial content follows.'),

    300:('Multiple Choices', 'Object has several resources -- see URI list'),
    301:('Moved Permanently', 'Object moved permanently -- see URI list'),
    302:('Found', 'Object moved temporarily -- see URI list'),
    303:('See Other', 'Object moved -- see Method and URL list'),
    304:('Not Modified', 'Document has not changed since given time'),
    305:('Use Proxy',
          'You must use proxy specified in Location to access this resource.'),
    307:('Temporary Redirect', 'Object moved temporarily -- see URI list'),

    400:('Bad Request', 'Bad request syntax or unsupported method'),
    401:('Unauthorized', 'No permission -- see authorization schemes'),
    402:('Payment Required', 'No payment -- see charging schemes'),
    403:('Forbidden', 'Request forbidden -- authorization will not help'),
    404:('Not Found', 'Nothing matches the given URI'),
    405:('Method Not Allowed', 'Specified method is invalid for this server.'),
    406:('Not Acceptable', 'URI not available in preferred format.'),
    407:('Proxy Authentication Required',
          'You must authenticate with this proxy before proceeding.'),
    408:('Request Timeout', 'Request timed out; try again later.'),
    409:('Conflict', 'Request conflict.'),
    410:('Gone', 'URI no longer exists and has been permanently removed.'),
    411:('Length Required', 'Client must specify Content-Length.'),
    412:('Precondition Failed', 'Precondition in headers is false.'),
    413:('Request Entity Too Large', 'Entity is too large.'),
    414:('Request-URI Too Long', 'URI is too long.'),
    415:('Unsupported Media Type', 'Entity body in unsupported format.'),
    416:('Requested Range Not Satisfiable', 'Cannot satisfy request range.'),
    417:('Expectation Failed', 'Expect condition could not be satisfied.'),

    500:('Internal Server Error', 'Server got itself in trouble'),
    501:('Not Implemented', 'Server does not support this operation'),
    502:('Bad Gateway', 'Invalid responses from another server/proxy.'),
    503:('Service Unavailable',
          'The server cannot process the request due to a high load'),
    504:('Gateway Timeout',
          'The gateway server did not receive a timely response'),
    505:('HTTP Version Not Supported', 'Cannot fulfill request.'),
}

class HttpMessage(object):
    def __init__(self): self.headers = []

    def add_header(self, h, v):
        self.headers.append([h.lower(), v])

    def get_header(self, k, v=None):
        for ks, vs in self.headers:
            if ks == k: return vs
        return v

    def get_headers(self, k):
        return [vs for ks, vs in self.headers if ks == k]

    def has_header(self, k):
        for ks, vs in self.headers:
            if ks == k: return True
        return False

    def recv_header(self, stream):
        while True:
            line = stream.readline()
            if not line: raise EOFError()
            line = line.strip()
            if not line: break
            if line[0] not in (' ', '\t'):
                h, v = line.split(':', 1)
                self.add_header(h.strip(), v.strip())
            else: self.add_header(h.strip(), line.strip())

    def recv_body(self, stream, on_body, hasbody=False, raw=False):
        if self.get_header('transfer-encoding', 'identity') != 'identity':
            logger.debug('recv body on chunk mode')
            chunk_size = 1
            while chunk_size:
                line = stream.readline()
                chunk = line.split(';')
                chunk_size = int(chunk[0], 16)
                if raw: on_body(line + stream.read(chunk_size + 2))
                else: on_body(stream.read(chunk_size + 2)[:-2])
        elif self.has_header('content-length'):
            length = int(self.get_header('content-length'))
            logger.debug('recv body on length mode, size: %s' % length)
            for i in xrange(0, length, BUFSIZE):
                on_body(stream.read(min(length - i, BUFSIZE)))
        elif hasbody:
            logger.debug('recv body on close mode')
            d = stream.read(BUFSIZE)
            while d:
                on_body(d)
                d = stream.read(BUFSIZE)

class HttpRequest(HttpMessage):

    def __init__(self, method, uri, version):
        HttpMessage.__init__(self)
        self.method, self.uri, self.version = method, uri, version

class HttpResponse(HttpMessage):

    def __init__(self, version, code, phrase):
        HttpMessage.__init__(self)
        self.version, self.code, self.phrase = version, int(code), phrase
        self.closeconn = True

    def send(self, stream):
        start_line = [self.version, str(self.code), self.phrase]
        self.send_header(stream, start_line, self.headers)

def send_header(stream, start_line, headers):
    stream.write(" ".join(start_line) + '\r\n')
    for k, l in headers:
        k = '-'.join([t.capitalize() for t in k.split('-')])
        stream.write("%s: %s\r\n" % (k, l))
    stream.write('\r\n')

def recv(stream, cls=HttpRequest):
    line = stream.readline().strip()
    if len(line) == 0: raise EOFError()
    r = line.split(' ', 2)
    if len(r) < 3: r.append(DEFAULT_PAGES[int(r[1])][0])
    msg = cls(*r)
    msg.recv_header(stream)
    return msg

def print_header(d, start_line, headers):
    logger.debug(d + ' '.join(start_line))
    for k, v in headers: logger.debug(d + '%s: %s' % (k, v))

def parse_target(uri):
    u = urlparse(uri)
    if not u.netloc: hostname = u.path
    else: hostname = u.netloc
    r = hostname.split(':', 1)
    hostname = r[0]
    if len(r) > 1: port = int(r[1])
    else: port = 443 if u.scheme.lower() == 'https' else 80
    return hostname, port, u.path + '?' + u.query

def connect(req, stream, sock_factory):
    hostname, port, uri = parse_target(req.uri)
    with sock_factory(hostname, port) as sock:
        res = HttpResponse(req.version, 200, DEFAULT_PAGES[200][0])
        send_header(stream, (res.version, str(res.code), res.phrase), res.headers)
        stream.flush()

        rlist = [stream.fileno(), sock.fileno()]
        while True:
            for rfd in select.select(rlist, [], [])[0]:
                d = os.read(rfd, BUFSIZE)
                if rfd == stream.fileno():
                    os.write(sock.fileno(), d)
                else: os.write(stream.fileno(), d)

def http_proxy(req, stream, sock_factory):
    hostname, port, uri = parse_target(req.uri)
    headers = [(h, v) for h, v in req.headers if not h.lower().startswith('proxy')]
    with sock_factory(hostname, port) as sock:
        stream1 = sock.makefile()

        if VERBOSE:
            print_header('> ', (req.method, uri, req.version), headers)
        send_header(stream1, (req.method, uri, req.version), headers)
        req.recv_body(stream, stream1.write, raw=True)
        stream1.flush()

        res = recv(stream1, HttpResponse)
        if VERBOSE:
            print_header('< ', (res.version, str(res.code), res.phrase), res.headers)
        send_header(stream, (res.version, str(res.code), res.phrase), res.headers)
        hasbody = req.method.upper() != 'HEAD' and res.code not in CODE_NOBODY
        res.recv_body(stream1, stream.write, hasbody, raw=True)
        stream.flush()
    return req.get_header('proxy-connection', '').lower() == 'keep-alive'
