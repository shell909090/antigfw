#!/usr/bin/python
# -*- coding: utf-8 -*-
'''
@date: 2012-09-26
@author: shell.xu
'''
import sys, random, struct, logging
from gevent import socket

logger = logging.getLogger('netfilter')

def get_netaddr(ip, mask):
    return ''.join(map(lambda x, y: chr(ord(x) & ord(y)), ip, mask))

def makemask(num):
    s = 0
    for i in xrange(32):
        s <<= 1
        s |= i<num
    return struct.pack('>L', s)

class NetFilter(object):

    def __init__(self, filename=None):
        self.nets = {}
        if filename: self.loadfile(filename)

    def loadline(self, line):
        if line.find(' ') != -1:
            addr, mask = line.split(' ', 1)
        elif line.find('/') != -1:
            addr, mask = line.split('/', 1)
            mask = makemask(int(mask))
        addr, mask = socket.inet_aton(addr), socket.inet_aton(mask)
        self.nets.setdefault(mask, set())
        self.nets[mask].add(get_netaddr(addr, mask))

    def load(self, stream):
        for line in stream: self.loadline(line.strip())

    def loadfile(self, filename):
        openfile = open
        if filename.endswith('.gz'):
            import gzip
            openfile = gzip.open
        try:
            with openfile(filename) as fi: self.load(fi)
        except (OSError, IOError): return False

    def save(self, stream):
        r = []
        for mask, addrs in self.nets.iteritems():
            r.extend([(addr, mask) for addr in list(addrs)])
        for addr, mask in sorted(r, key=lambda x: x[0]):
            stream.write('%s %s\n' % (socket.inet_ntoa(addr), socket.inet_ntoa(mask)))

    def savefile(self, filepath):
        openfile = open
        if filepath.endswith('.gz'):
            import gzip
            openfile = gzip.open
        try:
            with openfile(filepath, 'w+') as fo: self.save(fo)
        except (OSError, IOError): return False

    def __contains__(self, addr):
        try: addr = socket.inet_aton(addr)
        except TypeError: pass
        for mask, addrs in self.nets.iteritems():
            if get_netaddr(addr, mask) in addrs: return True
        return False

def main():
    nf = NetFilter(sys.argv[1])
    for i in sys.argv[2:]: print '%s: %s' % (i, i in nf)

if __name__ == '__main__': main()
