#!/usr/bin/python
# -*- coding: utf-8 -*-
'''
@date: 2010-06-04
@author: shell.xu
'''
import sys, struct, getopt, logging, conn
from contextlib import contextmanager
from gevent import socket, coros

__all__ = ['SocksManager',]
logger = logging.getLogger('socks')

PROXY_TYPE_SOCKS4 = 1
PROXY_TYPE_SOCKS5 = 2

def fmt_string(data): return chr(len(data)) + data

class GeneralProxyError(socket.error):
    __ERRORS =("success", "invalid data", "not connected", "not available", "bad proxy type", "bad input")
    def __init__(self, id, *params):
        if id in self.__ERRORS: params.insert(0, self.__ERRORS[id])
        super(GeneralProxyError, self).__init__(*params)

class Socks4Error(GeneralProxyError):
    __ERRORS =("request granted", "request rejected or failed", "request rejected because SOCKS server cannot connect to identd on the client", "request rejected because the client program and identd report different user-ids", "unknown error")
    def __init__(self, *params):
        super(Socks4Error, self).__init__(*params)

class Socks5Error(GeneralProxyError):
    __ERRORS =("succeeded", "general SOCKS server failure", "connection not allowed by ruleset", "Network unreachable", "Host unreachable", "Connection refused", "TTL expired", "Command not supported", "Address type not supported", "Unknown error")
    def __init__(self, *params):
        super(Socks5Error, self).__init__(*params)

class Socks5AuthError(GeneralProxyError):
    __ERRORS =("succeeded", "authentication is required",
                "all offered authentication methods were rejected",
                "unknown username or invalid password", "unknown error")
    def __init__(self, *params):
        super(Socks5AuthError, self).__init__(*params)

def socks5_create(sock, proxyaddr, username=None, password=None):
    sock.connect(proxyaddr)
    stream = sock.makefile()

    # hand shake request
    if username is None or password is None:
        stream.write("\x05\x01\x00")
    else: stream.write("\x05\x02\x00\x02")
    stream.flush()
    
    # hand shake response
    chosenauth = stream.read(2)
    if len(chosenauth) == 0: raise EOFError()
    if chosenauth[0] != "\x05": raise GeneralProxyError(1)
    if chosenauth[1] == "\x00": pass
    elif chosenauth[1] == "\x02":
        stream.write('\x01' + fmt_string(username) + fmt_string(password))
        stream.flush()
        authstat = stream.read(2)
        if len(authstat) == 0: raise EOFError()
        if authstat[0] != "\x01": raise GeneralProxyError(1)
        if authstat[1] != "\x00": raise Socks5AuthError(3)
        logger.debug('authenticated with password')
    elif chosenauth[1] == "\xFF": raise Socks5AuthError(2)
    else: raise GeneralProxyError(1)

def socks5_connect(sock, target, rdns=True):
    stream = sock.makefile()
    # connect request
    try: reqaddr = "\x01" + socket.inet_aton(target[0])
    except socket.error:
        if rdns: reqaddr = '\x03' + fmt_string(target[0])
        else: reqaddr = "\x01" + socket.inet_aton(socket.gethostbyname(target[0]))
    s = "\x05\x01\x00" + reqaddr + struct.pack(">H", target[1])
    stream.write(s)
    stream.flush()

    # connect response
    resp = stream.read(4)
    if not resp: raise EOFError()
    if resp[0] != "\x05": raise GeneralProxyError(1)
    if resp[1] != "\x00":
        if ord(resp[1]) <= 8: raise Socks5Error(ord(resp[1]))
        else: raise Socks5Error(9)
    if resp[3] == "\x03": boundaddr = stream.read(stream.read(1))
    elif resp[3] == "\x01": boundaddr = socket.inet_ntoa(stream.read(4))
    else: raise GeneralProxyError(1)
    boundport = struct.unpack(">H", stream.read(2))[0]
    logger.debug('socks connected with %s:%s' % target)
    return boundaddr, boundport

def socks5(proxyaddr, username=None, password=None, rdns=True):
    def reciver(func):
        def creator(family=socket.AF_INET, type=socket.SOCK_STREAM, proto=0):
            sock = func(family, type, proto)
            socks5_create(sock, proxyaddr, username, password)
            def newconn(addr): socks5_connect(sock, addr, rdns)
            sock.connect, sock.connect_ex = newconn, newconn
            return sock
        return creator
    return reciver

class SocksManager(conn.Manager):

    def __init__(self, addr, port, username=None, password=None,
                 rdns=True, max_conn=10, name=None, ssl=False, **kargs):
        super(SocksManager, self).__init__(max_conn, name or 'socks5:%s:%s' % (addr, port))
        if ssl is True: self.creator = conn.ssl_socket()(self.creator)
        elif ssl: self.creator = conn.ssl_socket(ssl)(self.creator)
        self.creator = socks5((addr, port), username, password, rdns)(self.creator)
