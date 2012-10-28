#!/usr/bin/python
# -*- coding: utf-8 -*-
'''
@date: 2012-04-26
@author: shell.xu
'''
import logging

logger = logging.getLogger('http')

BUFSIZE = 8192
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

def dummy_write(d): return

def capitalize_httptitle(k):
    return '-'.join([t.capitalize() for t in k.split('-')])

class HttpMessage(object):
    def __init__(self): self.headers, self.body = [], None

    def add_header(self, k, v):
        self.headers.append([k, v])

    def set_header(self, k, v):
        for h in self.headers:
            if h[0] == k:
                h[1] = v
                return
        self.add_header(k, v)

    def get_header(self, k, v=None):
        for ks, vs in self.headers:
            if ks == k: return vs
        return v

    def get_headers(self, k):
        return [vs for ks, vs in self.headers if ks == k]

    def has_header(self, k): return self.get_header(k) is not None

    def send_header(self, stream):
        stream.write(self.get_startline() + '\r\n')
        for k, l in self.headers: stream.write("%s: %s\r\n" % (k, l))
        stream.write('\r\n')

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

    def read_chunk(self, stream, hasbody=False, raw=False):
        if self.get_header('Transfer-Encoding', 'identity') != 'identity':
            logger.debug('recv body on chunk mode')
            chunk_size = 1
            while chunk_size:
                line = stream.readline()
                chunk = line.split(';')
                chunk_size = int(chunk[0], 16)
                if raw: yield line + stream.read(chunk_size + 2)
                else: yield stream.read(chunk_size + 2)[:-2]
        elif self.has_header('Content-Length'):
            length = int(self.get_header('Content-Length'))
            logger.debug('recv body on length mode, size: %s' % length)
            for i in xrange(0, length, BUFSIZE):
                yield stream.read(min(length - i, BUFSIZE))
        elif hasbody:
            logger.debug('recv body on close mode')
            d = stream.read(BUFSIZE)
            while d:
                yield d
                d = stream.read(BUFSIZE)

    def read_body(self, hasbody=False, raw=False):
        return ''.join(self.read_chunk(self.stream, hasbody, raw))

    def read_form(self):
        return dict([i.split('=', 1) for i in self.read_body().split('&')])

    def sendto(self, stream, *p, **kw):
        self.send_header(stream)
        if self.body is None: return
        elif callable(self.body):
            for d in self.body(*p, **kw): stream.write(d)
        else: stream.write(self.body)

    def debug(self):
        logger.debug(self.d + self.get_startline())
        for k, v in self.headers: logger.debug('%s%s: %s' % (self.d, k, v))

class HttpRequest(HttpMessage):
    d = '> '

    def __init__(self, method, uri, version):
        HttpMessage.__init__(self)
        self.method, self.uri, self.version = method, uri, version

    def get_startline(self):
        return ' '.join((self.method, self.uri, self.version))

class HttpResponse(HttpMessage):
    d = '< '

    def __init__(self, version, code, phrase):
        HttpMessage.__init__(self)
        self.version, self.code, self.phrase = version, int(code), phrase
        self.connection, self.cache = False, 0

    def __nonzero__(self): return self.connection

    def get_startline(self):
        return ' '.join((self.version, str(self.code), self.phrase))

def recv_msg(stream, cls):
    line = stream.readline().strip()
    if len(line) == 0: raise EOFError()
    r = line.split(' ', 2)
    if len(r) < 2: raise Exception('unknown format')
    if len(r) < 3: r.append(DEFAULT_PAGES[int(r[1])][0])
    msg = cls(*r)
    msg.stream = stream
    msg.recv_header(stream)
    return msg

def request_http(uri, method=None, version=None, headers=None, data=None):
    if not method: method = 'GET' if data is None else 'POST'
    if not version: version = 'HTTP/1.1'
    if not headers: headers = []
    req = HttpRequest(method, uri, version)
    req.headers, req.body = headers, data
    if req.body and isinstance(req.body, basestring):
        req.set_header('Content-Length', str(len(req.body)))
    return req

def response_http(code, phrase=None, version=None, headers=None,
                  cache=0, body=None):
    if not phrase: phrase = DEFAULT_PAGES[code][0]
    if not version: version = 'HTTP/1.1'
    res = HttpResponse(version, code, phrase)
    if body and isinstance(body, basestring):
        res.set_header('Content-Length', str(len(body)))
    if headers:
        for k, v in headers: res.set_header(k, v)
    res.cache, res.body = cache, body
    return res

def http_client(req, addr, creator):
    sock = creator()
    sock.connect(addr)
    try:
        stream = sock.makefile()
        req.sendto(stream)
        stream.flush()
        return recv_msg(stream, HttpResponse)
    finally: sock.close()
