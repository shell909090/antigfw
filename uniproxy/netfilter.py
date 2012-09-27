#!/usr/bin/python
# -*- coding: utf-8 -*-
'''
@date: 2012-09-26
@author: shell.xu
'''
import os, sys, time, heapq, random, struct, logging
from contextlib import contextmanager
from gevent import socket, coros
import DNS

logger = logging.getLogger('netfilter')

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
    rslt = [i['data'] for i in r.answers if i['typename'] == 'A']
    logger.info('resolve %s to %s' % (name, str(rslt)))
    return rslt

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

    def get(self, k):
        n = self.__dict.get(k)
        if n is None: return None
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
    DNSPORT   = 53
    TIMEOUT   = 3600
    RETRY     = 3

    def __init__(self, get_conn_mgr, dnsserver=None, cachesize=512, max_conn=10):
        self.dnsserver = dnsserver or self.DNSSERVER
        self.cache, self.cachesize = ObjHeap(cachesize), cachesize
        self.get_conn_mgr = get_conn_mgr
        self.smph, self.max_conn = coros.Semaphore(max_conn), max_conn

    def size(self): return self.max_conn - self.smph.counter
    def stat(self): return '%d/%d' % (self.size(), self.max_conn)

    def gethostbyname(self, name):
        if name in self.cache:
            if time.time() - self.cache[name][0] <= self.TIMEOUT:
                return random.choice(self.cache[name][1])
            else: del self.cache[name]

        for i in xrange(self.RETRY):
            try:
                with self.smph:
                    with self.get_conn_mgr(False).get_socket(
                        self.dnsserver, self.DNSPORT) as sock:
                        r = nslookup(sock, name)
                        self.cache[name] = (time.time(), r)
                        break
            except (EOFError, socket.error): pass

        r = self.cache.get(name)
        if r is None: return None
        else: return random.choice(r[1])

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
