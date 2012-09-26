#!/usr/bin/python
# -*- coding: utf-8 -*-
'''
@date: 2012-09-26
@author: shell.xu
'''
import os, sys, time, random
from gevent import socket
import DNS

def nslookup(sock, name):
    stream = sock.makefile()
    m = DNS.Mpacker()
    qtype = DNS.Type.A
    tid = random.randint(0,65535)
    m.addHeader(tid, 0, DNS.Opcode.QUERY, 0, 0, 1, 0, 0, 0, 1, 0, 0, 0)
    m.addQuestion(name, qtype, DNS.Class.IN)

    request = m.getbuf()
    stream.write(DNS.pack16bit(len(request)) + request)
    stream.flush()

    s = stream.read(2)
    if len(s) == 0: raise EOFError()
    count = DNS.unpack16bit(s)
    reply = stream.read(count)
    if len(reply) == 0: raise EOFError()

    u = DNS.Munpacker(reply)
    r = DNS.DnsResult(u, {})
    return [i['data'] for i in r.answers if i['typename'] == 'A']

class ObjHeap(object):
    ''' 使用lru算法的对象缓存容器，感谢Evan Prodromou <evan@bad.dynu.ca>。
    thx for Evan Prodromou <evan@bad.dynu.ca>. '''

    class __node(object):
        def __init__(self, k, v, f): self.k, self.v, self.f = k, v, f
        def __cmp__(self, o): return self.f > o.f

    def __init__(self, size):
        self.size, self.f = size, 0
        self.__dict, self.__heap = {}, []

    def __len__(self): return len(self.__dict)
    def __contains__(self, k): return self.__dict.has_key(k)

    def __setitem__(self, k, v):
        if self.__dict.has_key(k):
            n = self.__dict[k]
            n.v = v
            self.f += 1
            n.f = self.f
            heapq.heapify(self.__heap)
        else:
            while len(self.__heap) >= self.size:
                del self.__dict[heapq.heappop(self.__heap).k]
                self.f = 0
                for n in self.__heap: n.f = 0
            n = self.__node(k, v, self.f)
            self.__dict[k] = n
            heapq.heappush(self.__heap, n)

    def __getitem__(self, k):
        n = self.__dict[k]
        self.f += 1
        n.f = self.f
        heapq.heapify(self.__heap)
        return n.v

    def __delitem__(self, k):
        n = self.__dict[k]
        del self.__dict[k]
        self.__heap.remove(n)
        heapq.heapify(self.__heap)
        return n.v

    def __iter__(self):
        c = self.__heap[:]
        while len(c): yield heapq.heappop(c).k
        raise StopIteration

class DNSServer(object):
    DNSSERVER = '8.8.8.8'
    TIMEOUT = 3600
    RETRY = 3

    def __init__(self, sock_factory, dnsserver=None, cachesize=1000):
        self.dnsserver = dnsserver or self.DNSSERVER
        self.cache = ObjHeap(cachesize)
        self.sock, self.sock_factory = None, sock_factory
        self.reconnect()

    def reconnect(self):
        if self.sock: self.sock_factory.release(self.sock)
        self.sock = self.sock_factory.acquire()

    def gethostbyname(self, name):
        if name in self.cache:
            if time.time() - self.cache[name][0] <= self.TIMEOUT:
                return random.choice(self.cache[name][1])
            else: del self.cache[name]
        for i in xrange(self.RETRY):
            try:
                r = nslookup(self.sock, name)
                self.cache[name] = (time.time(), r)
                break
            except EOFError: self.reconnect()
        return random.choice(self.cache[name][1])

def get_netaddr(ip, mask):
    return ''.join(map(lambda x, y: chr(ord(x) & ord(y)), ip, mask))

class NetFilter(object):

    def __init__(self, filename=None):
        self.nets = {}
        if filename: self.loadfile(filename)

    def loadline(self, line):
        if line.find(' ') != -1:
            addr, mask = line.split(' ', 1)
        elif line.find('/') != -1:
            addr, mask = line.split('/', 1)
            raise Exception('not impl yet')
        addr, mask = socket.inet_aton(addr), socket.inet_aton(mask)
        self.nets.setdefault(mask, set())
        self.nets[mask].add(get_netaddr(addr, mask))

    def loadfile(self, filename):
        openfile = open
        if filename.endswith('.gz'):
            import gzip
            openfile = gzip.open
        with openfile(filename) as fi:
            for line in fi: self.loadline(line.strip())
            
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
