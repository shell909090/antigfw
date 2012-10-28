#!/usr/bin/python
# -*- coding: utf-8 -*-
'''
@date: 2012-09-28
@author: shell.xu
'''
import os, sys, struct, socket, logging

DNSSERVER = '8.8.8.8'

def initlog(lv, logfile=None):
    rootlog = logging.getLogger()
    if logfile: handler = logging.FileHandler(logfile)
    else: handler = logging.StreamHandler()
    handler.setFormatter(
        logging.Formatter(
            '%(asctime)s,%(msecs)03d %(name)s[%(levelname)s]: %(message)s',
            '%H:%M:%S'))
    rootlog.addHandler(handler)
    rootlog.setLevel(lv)

def on_datagram(data):
    sock = socket.socket()
    try:
        sock.connect((DNSSERVER, 53))
        stream = sock.makefile()

        s = struct.pack('!H', len(data))
        stream.write(s+data)
        stream.flush()

        s = stream.read(2)
        if len(s) == 0: raise EOFError()
        count = struct.unpack('!H', s)[0]
        reply = stream.read(count)
        if len(reply) == 0: raise EOFError()
    finally: sock.close()
    return reply

def server(port=53):
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(('', port))
    logging.info('init DNS Server')

    while True:
        data, addr = sock.recvfrom(1024)
        logging.debug('data come in from %s' % str(addr))
        try:
            r = on_datagram(data)
            if r is None: continue
            sock.sendto(r, addr)
        except Exception, err: logging.exception(err)

def main():
    initlog(logging.DEBUG)
    server()

if __name__ == '__main__': main()
