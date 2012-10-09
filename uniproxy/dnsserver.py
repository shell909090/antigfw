#!/usr/bin/python
# -*- coding: utf-8 -*-
'''
@date: 2012-09-29
@author: shell.xu
'''
import sys, time, heapq, random, getopt, logging, gevent, mydns
from gevent import socket, event

logger = logging.getLogger('dnsserver')

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

    def __init__(self, dnsserver=None, cachesize=512, timeout=30):
        self.dnsserver = dnsserver or self.DNSSERVER
        self.cache, self.cachesize = ObjHeap(cachesize), cachesize
        self.timeout = timeout
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.fakeset = set()
        self.inquery = {}
        gevent.spawn(self.receiver)

    def empty(self): self.fakeset = set()

    def load(self, stream):
        for line in stream:
            if line.startswith('#'): continue
            self.fakeset.add(line.strip())

    def loadfile(self, filename):
        openfile = open
        if filename.endswith('.gz'):
            import gzip
            openfile = gzip.open
        try:
            with openfile(filename) as fi: self.load(fi)
        except (OSError, IOError): return False

    def loadlist(self, filelist):
        for f in filelist: self.loadfile(f)

    def save(self, stream):
        for i in list(self.fakeset): stream.write(i+'\n')

    def savefile(self, filepath):
        openfile = open
        if filepath.endswith('.gz'):
            import gzip
            openfile = gzip.open
        try:
            with openfile(filepath, 'w+') as fo: self.save(fo)
        except (OSError, IOError): return False

    def gethostbyname(self, name):
        try:
            socket.inet_aton(name)
            return name
        except socket.error: pass

        if name in self.cache:
            if time.time() - self.cache[name][0] <= self.TIMEOUT:
                return random.choice(self.cache[name][1])
            else: del self.cache[name]

        self.query(name)
        r = self.cache.get(name)
        if r is None: return None
        else: return random.choice(r[1])

    def query(self, name, type=mydns.TYPE.A):
        q = mydns.mkquery((name, type))
        while q.id in self.inquery: q = mydns.mkquery((name, type))
        ar = event.AsyncResult()
        self.inquery[q.id] = (q, ar)

        self.sock.sendto(q.pack(), (self.dnsserver, self.DNSPORT))
        for i in xrange(self.RETRY):
            try:
                r = ar.get()
                del self.inquery[q.id]
                ipaddrs = [rdata for n, t, cls, ttl, rdata in r.ans if t == mydns.TYPE.A]
                if self.fakeset and any(map(lambda ip: ip in self.fakeset, ipaddrs)):
                    logger.info('drop %s in fakeset.' % ipaddrs)
                    continue
            except (EOFError, socket.error): continue
            self.cache[name] = (time.time(), ipaddrs)
            break

    def receiver(self):
        while True:
            try:
                while True:
                    d = self.sock.recvfrom(1024)[0]
                    r = mydns.Record.unpack(d)
                    if r.id not in self.inquery:
                        logger.warn('dns server got a record but don\'t know who care it\s id')
                    else:
                        self.inquery[r.id][1].set(r)
            except Exception, err: logger.exception(err)

    # def on_datagram(self, data):
    #     with self.smph:
    #         with self.get_conn_mgr(False).get_socket(self.dnsserver, self.DNSPORT) as sock:
    #             stream = sock.makefile()
    #             s = DNS.pack16bit(len(data))
    #             stream.write(s+data)
    #             stream.flush()

    #             s = stream.read(2)
    #             if len(s) == 0: raise EOFError()
    #             count = DNS.unpack16bit(s)
    #             reply = stream.read(count)
    #             if len(reply) == 0: raise EOFError()
    #     return reply

    # def server(self, port=53):
    #     sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    #     sock.bind(('', port))
    #     logger.info('init DNS Server')

    #     while True:
    #         data, addr = sock.recvfrom(1024)
    #         logger.debug('data come in from %s' % str(addr))
    #         try:
    #             r = self.on_datagram(data)
    #             if r is None: continue
    #             sock.sendto(r, addr)
    #         except Exception, err: logger.exception(err)

def main():
    optlist, args = getopt.getopt(sys.argv[1:], 'df')
    optdict = dict(optlist)
    if '-d' in optdict: return
    dnsfake = ['../dnsfake']
    if '-f' in optdict: dnsfake.insert(0, optdict['-f'])
    dns = DNSServer()
    dns.loadlist(dnsfake)
    for arg in args: print arg, dns.gethostbyname(arg)

if __name__ == '__main__': main()
