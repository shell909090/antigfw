#!/usr/bin/python
# -*- coding: utf-8 -*-
'''
@date: 2012-04-26
@author: shell.xu
'''
import logging

logger = logging.getLogger('http')

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

def dummy_write(d): return

class HttpMessage(object):
    def __init__(self): self.headers = []

    def add_header(self, k, v):
        self.headers.append([k.lower(), v])

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

    def recv_body(self, stream, on_body=dummy_write, hasbody=False, raw=False):
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

    def dbg_print(self):
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

    def get_startline(self):
        return ' '.join((self.version, str(self.code), self.phrase))

    def sendto(self, stream):
        stream.write(self.get_startline() + '\r\n')
        send_headers(stream, self.headers)

def send_headers(stream, headers):
    for k, l in headers:
        k = '-'.join([t.capitalize() for t in k.split('-')])
        stream.write("%s: %s\r\n" % (k, l))
    stream.write('\r\n')

def recv_headers(stream, cls=HttpRequest):
    line = stream.readline().strip()
    if len(line) == 0: raise EOFError()
    r = line.split(' ', 2)
    if len(r) < 2: raise Exception('unknown format')
    if len(r) < 3: r.append(DEFAULT_PAGES[int(r[1])][0])
    msg = cls(*r)
    msg.recv_header(stream)
    return msg

def response_http(req, stream, code, phrase=None, body=None):
    req.recv_body(stream)
    if not phrase: phrase = DEFAULT_PAGES[code][0]
    res = HttpResponse(req.version, code, phrase)
    if body: res.set_header('content-length', str(len(body)))
    res.sendto(stream)
    if body: stream.write(body)
    stream.flush()
